from .exception import *
from .items import *
from .jobs import *
from .logger import *
from .matrixHandler import *
from .routeHandler import *
from .geoCodingHandler import *
from . import matrixService
from .scenario import Scenario, ScenarioSolver, ScenarioException
from . import convertX

import osm_data as osm
import os
import threading
import time
from pydantic import TypeAdapter


DEFAULT_CONF = {
    'maxProblems': 2,               # solver processes
    'maxQueueSize': 50,             # open (waiting or running) problems
    'maxInactivityTime': 43200,     # seconds - unfetched results are deleted afterwards
    'serviceIntervall': 30,         # seconds between two cleanups
    'maxPollingPause': 0,           # seconds - open problems are cancelled if their status is not requested (0: off)
    'runTimeGrace': 60,             # seconds added to maxSolvingTime for the watchdog
    'defaultMaxRunTime': 600,       # seconds - watchdog limit for problems without maxSolvingTime
    'workDir': None,                # working directory of the solver processes (files of CMPL and the solvers)
    'matrixCache': True,            # raw OSM matrices in a SQLite file - default: matrixCache.sqlite in workDir
    'matrixCacheFile': None,
    'matrixCacheMaxAge': 180,       # days - safety net, an update of the ORS servers invalidates the entries anyway
    'matrixCacheMaxEntries': 500,   # least recently used entries are deleted
    'tsp': {},
    'tpp': {},
}

problemAdapter = TypeAdapter(ProblemItem)


class LogisticsLabCore:
    """ optimisation problems and geo services without a transport layer

        Used by the REST server and by the local stdio interface.
        Data can be passed as items (see items.py) or as dicts, dicts are validated.
    """

    def __init__(self, conf=None, logger=None, osmConfigFile=None, osmLogFile=None, onStatusChange=None):
        self.conf = {**DEFAULT_CONF, **(conf or {})}
        for type in PROBLEM_ITEMS:
            self.conf.setdefault(type, {})
        self.logger = logger or CoreLogger()

        if osmConfigFile:
            osm.Config(optFile=osmConfigFile, logFile=osmLogFile)

        # matrices of /v1/matrix in this process, of the problems in the solver processes (worker.py)
        if not self.conf.get('matrixCacheFile') and self.conf.get('workDir'):
            self.conf['matrixCacheFile'] = os.path.join(self.conf['workDir'], 'matrixCache.sqlite')
        matrixService.configure(self.conf, self.logger)
        if self.conf.get('matrixCache') and self.conf.get('matrixCacheFile'):
            self.logger.info('core', f"matrix cache {self.conf['matrixCacheFile']} - "
                                     f"{self.conf['matrixCacheMaxAge']} days, {self.conf['matrixCacheMaxEntries']} entries")

        self.jobs = JobManager(self.conf, self.logger, onStatusChange)
        self.__scenarioSolvers = {}        # job id -> ScenarioSolver of the problems of submitScenario
        self.__lock = threading.Lock()

    #*********** optimisation problems ************

    def submit(self, problem, type=None, owner=None, maxOpenProblems=None):
        """ adds a problem to the queue and returns its id

            problem: item of PROBLEM_ITEMS or dict - a dict needs the field type, if type is not given
        """
        if isinstance(problem, dict):
            if type:
                problem = PROBLEM_ITEMS[type].model_validate(problem)
            else:
                problem = problemAdapter.validate_python(problem)
        return self.jobs.submit(problem.type, problem, owner=owner, maxOpenProblems=maxOpenProblems)

    def submitScenario(self, request, owner=None, maxOpenProblems=None):
        """ adds a problem of a scenario (llab) to the queue and returns its id

            request: {scenario: {...llab}, problem: name (default: the first problem), parameters: {...} (optional)}
            The matrix of the problem is calculated before (OSM servers or cache). fetch returns the solution document
            (llsol) of the problem additionally as field solution.
        """
        if not isinstance(request, dict) or not isinstance(request.get('scenario'), dict):
            raise LogLabCoreException('scenario is missing', 422)
        try:
            scenario = Scenario.model_validate(request['scenario'])
        except ValueError as e:
            raise LogLabCoreException(f'invalid scenario: {e}', 422)
        name = request.get('problem')
        problems = [ p for p in scenario.problems if name is None or p.name == name ]
        if not problems:
            raise LogLabCoreException(f'problem {name} not found in the scenario' if name else
                                      'the scenario has no problems', 400)
        solver = ScenarioSolver(scenario, _CoreBackend(self))
        try:
            payload = solver.prepare(problems[0], request.get('parameters'))
        except ScenarioException as e:
            raise LogLabCoreException(str(e), 400)
        id = self.submit(payload, owner=owner, maxOpenProblems=maxOpenProblems)
        with self.__lock:
            # solvers of problems deleted without fetch (maxInactivityTime) are removed here
            self.__scenarioSolvers = { k: v for k, v in self.__scenarioSolvers.items() if self.jobs.get(k) }
            self.__scenarioSolvers[id] = solver
        return id

    def convert(self, request):
        """ scenario (llab) of an old LogisticsLab file (TPPX, TSPX, CLPX, DLPX, NWFX, VRPX) - see convertX.py

            request: {fileName: e.g. drogma.CLPX (the extension is the format), content: text of the file}
            returns {scenario: {...}, fileName: e.g. drogma.clpx.llab}
        """
        if not isinstance(request, dict) or not isinstance(request.get('fileName'), str) \
                or not isinstance(request.get('content'), str):
            raise LogLabCoreException('fileName and content are needed', 422)
        name = os.path.basename(request['fileName'].replace('\\', '/'))
        try:
            scenario = convertX.convertText(request['content'], name)
        except convertX.SkipFile as e:
            raise LogLabCoreException(f'not converted: {e}', 422)
        except Exception as e:                       # broken files - wrong sections, numbers, ...
            raise LogLabCoreException(f'{name} cannot be converted: {e}', 400)
        return {'scenario': scenario, 'fileName': convertX.targetName(name)}

    def fetch(self, id, owner=None):
        """ status of a problem and its results if it is finished - a finished problem is deleted afterwards

            returns (dict, httpStatus, job) - raises LogLabCoreException if the id is unknown or belongs to another owner
        """
        job = self.jobs.get(id)
        if job is None or job.owner != owner:
            raise LogLabCoreException(f'problem id: {id} not found', 400)

        job.lastAccess = time.time()
        ret = job.toDict(withResults=True)
        if job.status in FINISHED:
            self.jobs.delete(id)
            with self.__lock:
                solver = self.__scenarioSolvers.pop(id, None)
            if solver:
                ret['solution'] = solver.finish(ret)
        return ret, job.httpStatus, job

    def cancel(self, id, owner=None):
        job = self.jobs.get(id)
        if job is None or job.owner != owner:
            raise LogLabCoreException(f'problem id: {id} not found', 400)
        self.jobs.cancel(id)
        return job.toDict()

    def shutdown(self):
        self.jobs.shutdown()

    #*********** geo services ************

    def geo(self, service, request):
        """ matrix, routing, coordinates, search or reverse - returns a dict with message and the results

            raises LogLabCoreException with the http status of the OSM request if it fails
        """
        if service not in GEO_ITEMS:
            raise LogLabCoreException(f'unknown service {service}', 400)
        if isinstance(request, dict):
            request = GEO_ITEMS[service].model_validate(request)

        if service == 'matrix':
            h = MatrixHandler(request, self.logger)
            content = h.content
        elif service == 'routing':
            h = RouteHandler(request, self.logger)
            content = {'route': h.route}
        else:
            h = GeoCodingHandler(request, self.logger, service)
            if service == 'coordinates':
                content = {'coordinates': h.results, 'hits': h.hits}
            else:
                content = {'results': h.results}

        if h.status != 'ok':
            raise LogLabCoreException(h.message, h.httpStatus)
        return {'message': h.message, **content}


class _CoreBackend:
    """ matrix of ScenarioSolver.prepare from the geo services of the core """

    def __init__(self, core):
        self.core = core

    def matrix(self, payload):
        try:
            return self.core.geo('matrix', payload)
        except LogLabCoreException as e:
            raise ScenarioException(f'matrix: {e}')

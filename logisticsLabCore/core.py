from .exception import *
from .items import *
from .jobs import *
from .logger import *
from .matrixHandler import *
from .routeHandler import *
from .geoCodingHandler import *

import osm_data as osm
from pydantic import TypeAdapter


DEFAULT_CONF = {
    'maxProblems': 2,               # solver processes
    'maxQueueSize': 50,             # open (waiting or running) problems
    'maxInactivityTime': 43200,     # seconds - unfetched results are deleted afterwards
    'serviceIntervall': 30,         # seconds between two cleanups
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

        self.jobs = JobManager(self.conf, self.logger, onStatusChange)

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

    def fetch(self, id, owner=None):
        """ status of a problem and its results if it is finished - a finished problem is deleted afterwards

            returns (dict, httpStatus, job) - raises LogLabCoreException if the id is unknown or belongs to another owner
        """
        job = self.jobs.get(id)
        if job is None or job.owner != owner:
            raise LogLabCoreException(f'problem id: {id} not found', 400)

        ret = job.toDict(withResults=True)
        if job.status in FINISHED:
            self.jobs.delete(id)
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
            if request.matrixMode == 'distances':
                content = {'distances': h.distances}
            elif request.matrixMode == 'durations':
                content = {'durations': h.durations}
            else:
                content = {'distances': h.distances, 'durations': h.durations}
        elif service == 'routing':
            h = RouteHandler(request, self.logger)
            content = {'route': h.route}
        else:
            h = GeoCodingHandler(request, self.logger, service)
            content = {'coordinates' if service == 'coordinates' else 'results': h.results}

        if h.status != 'ok':
            raise LogLabCoreException(h.message, h.httpStatus)
        return {'message': h.message, **content}

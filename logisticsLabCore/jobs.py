from .exception import *
from .items import *
from .worker import workerMain, HANDLERS

import atexit
import multiprocessing
import os
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid


# status of finished jobs - their results are waiting to be fetched by the client
FINISHED = ('solution', 'noSolution', 'error', 'cancelled')
# status of jobs that occupy the queue or a solver process
OPEN = ('waiting', 'running')


class Job:
    def __init__(self, id, type, data, owner=None):
        if type not in HANDLERS:
            raise LogLabCoreException(f'wrong type {type}')
        self.id = id
        self.type = type
        self.data = data
        self.owner = owner                  # e.g. the name of the api key that has submitted the job
        self.status = 'waiting'
        self.message = 'Problem is waiting in queue'
        self.httpStatus = 200
        self.results = None
        self.size = ''
        self.createdTime = time.time()
        self.startedTime = None             # sent to a solver process
        self.finishedTime = None
        self.lastAccess = self.createdTime  # last request of the client for this job
        self.maxRunTime = None              # seconds in a solver process, afterwards the watchdog stops the job
        self.dispatched = False             # has been sent to a solver process
        self.cancelRequested = False
        self.cancelMessage = 'Problem has been cancelled'

    def finish(self, status, message, httpStatus, results=None):
        self.status = status
        self.message = message
        self.httpStatus = httpStatus
        self.results = results
        self.finishedTime = time.time()

    def toDict(self, withResults=False):
        d = {'id': self.id, 'status': self.status, 'message': self.message}
        if withResults and self.status == 'solution':
            d['results'] = self.results
        return d


def killProcessTree(process):
    """ kills a solver process together with CMPL and the solvers it has started """
    if not process.is_alive():
        return
    try:
        if os.name == 'posix':
            # the worker has its own process group - never kill the group of the parent
            if os.getpgid(process.pid) == process.pid:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        else:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
    except Exception:
        process.kill()
    process.join(5)


TMP_PREFIX = 'logisticsLab_'

def removeOrphanedTmpDirs():
    """ temp directories of solver processes of a server or app that has crashed - logisticsLab_<pid of the parent>_* """
    base = tempfile.gettempdir()
    for name in os.listdir(base):
        parts = name.split('_')
        if len(parts) < 3 or parts[0] + '_' != TMP_PREFIX or not parts[1].isdigit() or int(parts[1]) == os.getpid():
            continue
        if not isProcessAlive(int(parts[1])):
            shutil.rmtree(os.path.join(base, name), ignore_errors=True)

def isProcessAlive(pid):
    if os.name == 'posix':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            pass                # process of another user
        return True
    r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True)
    return str(pid) in r.stdout


class WorkerSlot:
    """ a solver process and the thread in the parent that feeds it with jobs """

    def __init__(self, manager, index):
        self.__manager = manager
        self.__index = index
        self.__process = None
        self.__conn = None
        self.__tmpDir = None
        self.__start()
        threading.Thread(target=self.__run, daemon=True).start()

    # seconds a new solver process has to report that it is ready - otherwise it is replaced (Windows: a spawned
    # process sometimes does not come up)
    STARTUP_TIMEOUT = 60
    STARTUP_TRIES = 3

    def __start(self):
        self.__started = False
        ctx = multiprocessing.get_context('spawn')
        self.__conn, childConn = ctx.Pipe()
        self.__tmpDir = tempfile.mkdtemp(prefix=f'{TMP_PREFIX}{os.getpid()}_')
        self.__process = ctx.Process(target=workerMain, args=(childConn, self.__manager.conf, self.__tmpDir), daemon=True)
        self.__process.start()
        childConn.close()

    def __kill(self):
        killProcessTree(self.__process)
        shutil.rmtree(self.__tmpDir, ignore_errors=True)

    def __restart(self):
        self.__kill()
        self.__start()

    def stop(self):
        self.__kill()

    def __waitForStart(self):
        """ waits until the solver process reports that it is ready - a process that does not report within
            STARTUP_TIMEOUT seconds or ends is replaced; False if no process starts after STARTUP_TRIES tries """
        m = self.__manager
        for attempt in range(1, self.STARTUP_TRIES + 1):
            deadline = time.time() + self.STARTUP_TIMEOUT
            while not self.__started and time.time() < deadline and self.__process.is_alive():
                try:
                    if self.__conn.poll(0.2):
                        msg = self.__conn.recv()
                        if msg[0] == 'started':
                            self.__started = True
                        elif msg[0] == 'log':
                            _, level, module, message = msg
                            getattr(m.logger, level)(module, message)
                except (EOFError, OSError):
                    break
            if self.__started:
                return True
            alive = self.__process.is_alive()
            m.logger.error('jobs', f'solver process {self.__index} (pid {self.__process.pid}) has not started - '
                                   f'{"still running after " + str(self.STARTUP_TIMEOUT) + "s" if alive else "ended with exit code " + str(self.__process.exitcode)}'
                                   f' - try {attempt} of {self.STARTUP_TRIES}, restarted')
            self.__restart()
        return False

    def __run(self):
        m = self.__manager
        while True:
            job = m.nextJob()
            if job is None:
                continue
            if not self.__started and not self.__waitForStart():
                m.finishJob(job, 'error', 'the solver process does not start', 500)
                continue
            try:
                job.startedTime = time.time()
                self.__conn.send((job.id, job.type, job.data))
                self.__waitForJob(job)
            except (EOFError, BrokenPipeError, OSError):
                m.finishJob(job, 'error', 'solver process has stopped unexpectedly', 500)
                m.logger.error('jobs', f'job {job.id} - {job.type} - solver process {self.__index} has stopped unexpectedly - restarted')
                self.__restart()

    def __waitForJob(self, job):
        m = self.__manager
        while True:
            if job.cancelRequested:
                self.__restart()
                m.finishJob(job, 'cancelled', job.cancelMessage, 200)
                m.logger.info('jobs', f'job {job.id} - {job.type} - {job.size} - cancelled - {job.cancelMessage}')
                return

            # watchdog - stops solvers that do not finish within their time limit
            if job.maxRunTime and time.time() - job.startedTime > job.maxRunTime:
                self.__restart()
                m.finishJob(job, 'error', f'time limit exceeded - the problem has been stopped after {job.maxRunTime}s', 504)
                m.logger.error('jobs', f'job {job.id} - {job.type} - {job.size} - time limit of {job.maxRunTime}s exceeded - solver process {self.__index} restarted')
                return

            if self.__conn.poll(0.2):
                msg = self.__conn.recv()
                kind = msg[0]

                if kind == 'log':
                    _, level, module, message = msg
                    getattr(m.logger, level)(module, message)

                elif kind == 'running':
                    job.size = msg[2]
                    m.setStatus(job, 'running', 'Problem is running')

                elif kind == 'done':
                    r = msg[2]
                    job.size = r['size']
                    if r['isSolution']:
                        results = {'objVal': r['objVal'], 'solvingTime': r['solvingTime'], **r['results']}
                        m.finishJob(job, 'solution', 'Solution has been found', 200, results)
                        m.logger.info('jobs', f"job {job.id} - {job.type} - {job.size} - solution - objVal {r['objVal']} - {r['solvingTime']}s")
                    else:
                        m.finishJob(job, 'noSolution', 'No solution has been found', 404)
                        m.logger.info('jobs', f"job {job.id} - {job.type} - {job.size} - noSolution - {r['solvingTime']}s")
                    return

                elif kind == 'error':
                    _, _, message, httpStatus, size = msg
                    job.size = size
                    m.finishJob(job, 'error', message, httpStatus)
                    m.logger.error('jobs', f"job {job.id} - {job.type}{' - '+size if size else ''} - {message}")
                    return

            elif not self.__process.is_alive():
                raise EOFError()


class JobManager:
    """ queue of optimisation problems, solved by conf['maxProblems'] solver processes

        conf:  maxProblems, maxQueueSize, maxInactivityTime, serviceIntervall, maxPollingPause,
               runTimeGrace, defaultMaxRunTime and a section per problem type (maxSolvingTime, maxRunTime, ...)
        onStatusChange(job) is called after every change of the status of a job
    """

    def __init__(self, conf, logger, onStatusChange=None):
        self.conf = conf
        self.logger = logger
        self.__onStatusChange = onStatusChange
        self.__jobs = {}
        # protects self.__jobs - it is used by the clients, the worker threads and the cleanup thread
        self.__lock = threading.Lock()
        self.__queue = queue.Queue()

        removeOrphanedTmpDirs()
        self.__slots = [ WorkerSlot(self, i) for i in range(conf['maxProblems']) ]
        threading.Thread(target=self.__cleanupWorker, daemon=True).start()
        atexit.register(self.shutdown)

        self.logger.debug('jobs', f"{conf['maxProblems']} solver processes have been started")

    #*********** used by the clients ************

    def submit(self, type, item, owner=None, maxOpenProblems=None):
        """ adds a problem (an item of PROBLEM_ITEMS) - raises LogLabLimitException if the queue or the owner has too many open jobs """
        data = item.model_dump()
        with self.__lock:
            openJobs = [ j for j in self.__jobs.values() if j.status in OPEN ]

            if len(openJobs) >= self.conf['maxQueueSize']:
                raise LogLabLimitException('server is busy - too many problems in queue, please try again later', 503)

            if maxOpenProblems is not None and sum(1 for j in openJobs if j.owner == owner) >= maxOpenProblems:
                raise LogLabLimitException(f'too many open problems - maximum is {maxOpenProblems}, please fetch the results first', 429)

            id = str(uuid.uuid4())
            job = Job(id, type, data, owner)
            job.maxRunTime = self.maxRunTime(type, data)
            self.__jobs[id] = job

        self.__queue.put(id)
        self.__notify(job)
        return id

    def get(self, id):
        """ returns the job or None """
        with self.__lock:
            return self.__jobs.get(id)

    def delete(self, id):
        with self.__lock:
            self.__jobs.pop(id, None)

    def cancel(self, id, message=None):
        """ cancels a waiting or running job - returns the job or None """
        with self.__lock:
            job = self.__jobs.get(id)
            if job is None or job.status not in OPEN:
                return job
            if message:
                job.cancelMessage = message
            if job.dispatched:
                job.cancelRequested = True      # the worker thread kills the solver process
                return job
            job.status = 'cancelled'            # not yet sent to a solver process - nextJob skips it
        self.finishJob(job, 'cancelled', job.cancelMessage, 200)
        self.logger.info('jobs', f'job {job.id} - {job.type} - cancelled while waiting - {job.cancelMessage}')
        return job

    def maxRunTime(self, type, data):
        """ time limit of the watchdog: maxRunTime of the problem type or the effective maxSolvingTime + runTimeGrace """
        c = self.conf.get(type, {})
        if c.get('maxRunTime'):
            return c['maxRunTime']
        solvingTime = data.get('maxSolvingTime')
        if c.get('maxSolvingTime'):
            solvingTime = min(solvingTime, c['maxSolvingTime']) if solvingTime else c['maxSolvingTime']
        return (solvingTime or self.conf['defaultMaxRunTime']) + self.conf['runTimeGrace']

    def shutdown(self):
        for slot in self.__slots:
            slot.stop()

    #*********** used by the worker threads ************

    def nextJob(self):
        """ next waiting job - cancelled or deleted jobs are skipped """
        id = self.__queue.get()
        with self.__lock:
            job = self.__jobs.get(id)
            if job is None or job.status != 'waiting':
                return None
            job.dispatched = True
            return job

    def setStatus(self, job, status, message):
        job.status = status
        job.message = message
        self.__notify(job)

    def finishJob(self, job, status, message, httpStatus, results=None):
        job.finish(status, message, httpStatus, results)
        self.__notify(job)

    def __notify(self, job):
        if self.__onStatusChange:
            try:
                self.__onStatusChange(job)
            except Exception as e:
                self.logger.error('jobs', f'status notification failed - {e}')

    #*********** cleanup ************

    def __cleanupWorker(self):
        """ deletes unfetched results and cancels abandoned jobs """
        while True:
            time.sleep(self.conf['serviceIntervall'])
            try:
                self.cleanup()
            except Exception as e:
                self.logger.error('jobs', f'cleanup failed - {e}')

    def cleanup(self):
        now = time.time()
        limit = now - self.conf['maxInactivityTime']
        pause = self.conf.get('maxPollingPause')
        with self.__lock:
            expired = [ id for id, j in self.__jobs.items() if j.status in FINISHED and j.finishedTime < limit ]
            for id in expired:
                del self.__jobs[id]
            # the client has not asked for the job within maxPollingPause - it has probably gone
            abandoned = [ id for id, j in self.__jobs.items() if pause and j.status in OPEN and now - j.lastAccess > pause ]

        for id in expired:
            self.logger.info('jobs', f'job {id} - results have not been fetched - deleted')
        for id in abandoned:
            self.cancel(id, f'Problem has been cancelled - the status has not been requested for more than {pause}s')

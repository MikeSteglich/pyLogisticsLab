from .exception import *
from .items import *
from .worker import workerMain, HANDLERS

import atexit
import multiprocessing
import os
import queue
import signal
import subprocess
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
        self.finishedTime = None
        self.dispatched = False             # has been sent to a solver process
        self.cancelRequested = False

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


class WorkerSlot:
    """ a solver process and the thread in the parent that feeds it with jobs """

    def __init__(self, manager, index):
        self.__manager = manager
        self.__index = index
        self.__process = None
        self.__conn = None
        self.__start()
        threading.Thread(target=self.__run, daemon=True).start()

    def __start(self):
        ctx = multiprocessing.get_context('spawn')
        self.__conn, childConn = ctx.Pipe()
        self.__process = ctx.Process(target=workerMain, args=(childConn, self.__manager.conf), daemon=True)
        self.__process.start()
        childConn.close()

    def __restart(self):
        killProcessTree(self.__process)
        self.__start()

    def stop(self):
        killProcessTree(self.__process)

    def __run(self):
        m = self.__manager
        while True:
            job = m.nextJob()
            if job is None:
                continue
            try:
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
                m.finishJob(job, 'cancelled', 'Problem has been cancelled', 200)
                m.logger.info('jobs', f'job {job.id} - {job.type} - {job.size} - cancelled')
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

        conf:  maxProblems, maxQueueSize, maxInactivityTime, serviceIntervall and a section per problem type
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

    def cancel(self, id):
        """ cancels a waiting or running job - returns the job or None """
        with self.__lock:
            job = self.__jobs.get(id)
            if job is None or job.status not in OPEN:
                return job
            if job.dispatched:
                job.cancelRequested = True      # the worker thread kills the solver process
                return job
            job.status = 'cancelled'            # not yet sent to a solver process - nextJob skips it
        self.finishJob(job, 'cancelled', 'Problem has been cancelled', 200)
        self.logger.info('jobs', f'job {job.id} - {job.type} - cancelled while waiting')
        return job

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
        """ deletes finished jobs whose results have not been fetched within maxInactivityTime """
        while True:
            time.sleep(self.conf['serviceIntervall'])
            self.cleanup()

    def cleanup(self):
        limit = time.time() - self.conf['maxInactivityTime']
        with self.__lock:
            expired = [ id for id, j in self.__jobs.items() if j.status in FINISHED and j.finishedTime < limit ]
            for id in expired:
                del self.__jobs[id]
        for id in expired:
            self.logger.info('jobs', f'job {id} - results have not been fetched - deleted')

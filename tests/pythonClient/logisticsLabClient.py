""" Python client of LogisticsLab - the same problems and results locally (stdio) and remotely (REST server)

    analog to tests/dartClient/lib/src/backend.dart - only the standard library is used

        with LocalBackend() as backend:                     # starts python -m logisticsLabCore.stdio
            answer = backend.solve({"type": "tsp", "distances": [...]})

        with RemoteBackend('http://127.0.0.1:8000/v1/', apiKey) as backend:
            answer = backend.solve({"type": "tsp", "distances": [...]})

    solve() returns the answer {id, status, message, results} - status solution, noSolution, error or cancelled.
    Rejected requests raise LogisticsLabException with the http status of the REST server (400, 403, 422 ...).
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from concurrent.futures import Future


PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
FINISHED = ('solution', 'noSolution', 'error', 'cancelled')


class LogisticsLabException(Exception):
    """ error of a request - httpStatus is the same for both backends """
    def __init__(self, httpStatus, message):
        super().__init__(message)
        self.httpStatus = httpStatus
        self.message = message

    def __str__(self):
        return f'LogisticsLabException({self.httpStatus}): {self.message}'


#*************** local: child process with JSON-RPC 2.0 over stdin/stdout ************************************

class LocalBackend:
    """ starts the local interface as child process and talks JSON-RPC with it

        python      interpreter with the packages of pyLogisticsLab (default: this interpreter)
        command     instead of python: the command of a bundled program, e.g. ['./logisticsLabLocal']
        logPath     log files, HiGHS.log and the matrix cache (default: logisticsLabPython in the temp directory)
    """

    def __init__(self, python=sys.executable, command=None, logPath=None, args=(), startTimeout=60):
        logPath = logPath or os.path.join(tempfile.gettempdir(), 'logisticsLabPython')
        self.__command = (list(command) if command else [python, '-m', 'logisticsLabCore.stdio']) \
                         + ['--logPath', logPath] + list(args)
        self.__startTimeout = startTimeout
        self.__process = None
        self.__nextId = 1
        self.__lock = threading.Lock()
        self.__pending = {}                 # request id -> Future
        self.__jobs = {}                    # problem id -> [Event (finished), last status, callback]
        self.__ready = threading.Event()

    def start(self):
        env = {**os.environ, 'PYTHONPATH': PROJECT_DIR}
        # stderr: log output of the core, CMPL and HiGHS - stdout belongs to the protocol only
        self.__process = subprocess.Popen(self.__command, cwd=PROJECT_DIR, env=env, stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          text=True, encoding='utf-8', bufsize=1)
        threading.Thread(target=self.__readStdout, daemon=True).start()
        if not self.__ready.wait(self.__startTimeout):
            self.close()
            raise LogisticsLabException(500, 'the local interface has not started')
        return self

    def __readStdout(self):
        """ one JSON-RPC message per line - answers to requests and notifications """
        for line in self.__process.stdout:
            msg = json.loads(line)
            if msg.get('id') is not None:                       # answer to a request
                with self.__lock:
                    future = self.__pending.pop(msg['id'], None)
                if future is None:
                    continue
                if 'error' in msg:
                    e = msg['error']
                    data = e.get('data') or {}
                    future.set_exception(LogisticsLabException(data.get('httpStatus', 500), e.get('message')))
                else:
                    future.set_result(msg['result'])
            elif msg.get('method') == 'ready':
                self.__ready.set()
            elif msg.get('method') == 'jobStatus':              # notification of a problem
                status = msg['params']
                job = self.__job(status['id'])
                job[1] = status
                if job[2]:
                    job[2](status)
                if status['status'] in FINISHED:
                    job[0].set()
        # the process has stopped - open requests fail
        with self.__lock:
            pending, self.__pending = self.__pending, {}
        for future in pending.values():
            future.set_exception(LogisticsLabException(500, 'the local process has stopped'))

    def __job(self, id):
        """ the notification can arrive before the answer of solve - the entry is created by the first of both """
        with self.__lock:
            return self.__jobs.setdefault(id, [threading.Event(), None, None])

    def call(self, method, params=None, timeout=None):
        """ JSON-RPC request - returns its result or raises LogisticsLabException """
        future = Future()
        with self.__lock:
            id = self.__nextId
            self.__nextId += 1
            self.__pending[id] = future
            self.__process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': id, 'method': method,
                                                   'params': params or {}}) + '\n')
            self.__process.stdin.flush()
        return future.result(timeout)

    #*********** problems ************

    def submit(self, problem, onStatus=None):
        """ submits a problem ({type: ..., ...}) - returns its id, onStatus(status) is called for every change """
        answer = self.call('solve', problem)
        job = self.__job(answer['id'])
        job[2] = onStatus
        if onStatus:
            onStatus(job[1] or answer)
        return answer['id']

    def wait(self, id, timeout=None):
        """ waits until the problem is finished - no polling, the process sends jobStatus """
        if not self.__job(id)[0].wait(timeout):
            raise TimeoutError(f'problem {id} is not finished after {timeout} s')

    def result(self, id):
        """ answer with the results - the problem is deleted afterwards """
        answer = self.call('result', {'id': id})
        with self.__lock:
            self.__jobs.pop(id, None)
        return answer

    def solve(self, problem, onStatus=None, timeout=None):
        id = self.submit(problem, onStatus)
        self.wait(id, timeout)
        return self.result(id)

    def status(self, id):
        return self.call('status', {'id': id})

    def cancel(self, id):
        return self.call('cancel', {'id': id})

    #*********** geo services: matrix, routing, coordinates, search, reverse ************

    def geo(self, service, params):
        return {'status': 'ok', **self.call(service, params)}

    def close(self):
        if self.__process is None:
            return
        try:
            if self.__process.poll() is None:
                self.call('shutdown', timeout=5)
        except Exception:
            pass
        try:
            self.__process.stdin.close()
            self.__process.wait(10)
        except Exception:
            self.__process.kill()
        self.__process = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


#*************** remote: REST server with api key ************************************

class RemoteBackend:
    """ the same interface for the REST server - the results are polled via /v1/results """

    def __init__(self, url='http://127.0.0.1:8000/v1/', apiKey='', pollInterval=0.3):
        self.url = url if url.endswith('/') else url + '/'
        self.apiKey = apiKey
        self.pollInterval = pollInterval
        self.__onStatus = {}                # problem id -> callback
        self.__finished = {}                # problem id -> answer of a finished problem

    def start(self):
        return self

    def post(self, endpoint, body, timeout=300):
        """ returns (http status, answer) """
        request = urllib.request.Request(self.url + endpoint, data=json.dumps(body).encode('utf-8'), method='POST',
                                         headers={'Content-Type': 'application/json', 'X-API-Key': self.apiKey})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as e:              # 4xx, 5xx - the body is the answer of the server
            return e.code, json.loads(e.read() or b'{}')

    def submit(self, problem, onStatus=None):
        code, answer = self.post('solve', problem)
        if code != 200:
            # rejected: 401/403 api key, 422 wrong fields, 429 too many problems, ...
            raise LogisticsLabException(code, answer.get('message') or answer.get('detail') or answer)
        self.__onStatus[answer['id']] = onStatus
        if onStatus:
            onStatus(answer)
        return answer['id']

    def wait(self, id, timeout=None):
        """ polls /v1/results - the answer of a finished problem is kept for result() """
        sTime = time.time()
        last = None
        while True:
            _, answer = self.post('results', {'id': id})
            onStatus = self.__onStatus.get(id)
            if onStatus and answer.get('status') != last:
                onStatus(answer)
            last = answer.get('status')
            if last in FINISHED or last is None:
                self.__finished[id] = answer
                return
            if timeout is not None and time.time() - sTime > timeout:
                raise TimeoutError(f'problem {id} is not finished after {timeout} s')
            time.sleep(self.pollInterval)

    def result(self, id):
        self.__onStatus.pop(id, None)
        return self.__finished.pop(id)

    def solve(self, problem, onStatus=None, timeout=None):
        id = self.submit(problem, onStatus)
        self.wait(id, timeout)
        return self.result(id)

    def status(self, id):
        raise NotImplementedError('the REST server reports the status via /v1/results - use wait()')

    def cancel(self, id):
        return self.post('cancel', {'id': id})[1]

    def geo(self, service, params):
        code, answer = self.post(service, params)
        if code != 200:
            raise LogisticsLabException(code, answer.get('message') or answer.get('detail') or answer)
        return answer

    def close(self):
        pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


def loadEnv(fileName=os.path.join(PROJECT_DIR, 'tests', 'serverTests', '.env')):
    """ environment variables, completed by the KEY=VALUE lines of tests/serverTests/.env (createTestKeys.py) """
    env = dict(os.environ)
    if os.path.isfile(fileName):
        with open(fileName, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    name, value = line.split('=', 1)
                    env.setdefault(name.strip(), value.strip())
    return env

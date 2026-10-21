""" local interface of LogisticsLab for desktop apps - JSON-RPC 2.0 over stdin/stdout

    python -m logisticsLabCore.stdio [--logPath DIR] [--osmConfig FILE] [--maxProblems N] [--debug] [--noMatrixCache]

    One JSON message per line (UTF-8). stdout is used only for the protocol - all other output goes to stderr.
    The process stops when stdin is closed or after the method shutdown.

    requests (app -> process)        result
      solve      {type, ...problem}    {id, status, message}   type: tsp, tpp, wlp, pmedian, pcentre, contpmedian,
                                                                  contpcentre, scp, mcp, cpp, vrp,
                                                                  mincostflow, maxflow, multicommodity, multimodal,
                                                                  multistagewlp
      status     {id}                  {id, status, message}
      result     {id}                  {id, status, message, results?}   finished problems are deleted afterwards
      cancel     {id}                  {id, status, message}
      matrix | routing | coordinates | search | reverse   {...}   {message, ...results}
      version    {}                    {version, protocol}
      shutdown   {}                    {}

    notifications (process -> app)
      ready      {version, protocol}           the process is ready for requests
      jobStatus  {id, status, message}         after every change of the status of a problem

    errors
      -32700 parse error, -32600 invalid request, -32601 unknown method, -32603 internal error
      -32602 invalid params      data: {httpStatus: 422, errors: [...]}
      -32000 problem/geo error   data: {httpStatus: 400 | 404 | 429 | 503 | ...}
"""

from . import __version__
from .core import *
from .logger import *
from . import paths

import argparse
import concurrent.futures
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
import traceback

import pydantic


PROTOCOL_VERSION = 1

GEO_METHODS = ('matrix', 'routing', 'coordinates', 'search', 'reverse')


class RpcError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


class StdioServer:
    def __init__(self, out):
        self.__out = out
        self.__lock = threading.Lock()
        self.__executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.core = None
        self.stopped = threading.Event()

    #*********** messages ************

    def send(self, msg):
        line = json.dumps({'jsonrpc': '2.0', **msg}, ensure_ascii=False)
        with self.__lock:
            self.__out.write(line + '\n')
            self.__out.flush()

    def notify(self, method, params):
        self.send({'method': method, 'params': params})

    def notifyStatus(self, job):
        self.notify('jobStatus', job.toDict())

    #*********** requests ************

    def handleLine(self, line):
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            self.send({'id': None, 'error': {'code': -32700, 'message': f'parse error: {e}'}})
            return

        if not isinstance(msg, dict) or not isinstance(msg.get('method'), str):
            self.send({'id': msg.get('id') if isinstance(msg, dict) else None,
                       'error': {'code': -32600, 'message': 'invalid request'}})
            return

        # geo requests wait for the OSM servers - all requests are handled in threads
        self.__executor.submit(self.__handle, msg)

    def __handle(self, msg):
        id = msg.get('id')
        try:
            result = self.__call(msg['method'], msg.get('params') or {})
            response = {'result': result}
        except RpcError as e:
            response = {'error': {'code': e.code, 'message': str(e), **({'data': e.data} if e.data else {})}}
        except pydantic.ValidationError as e:
            response = {'error': {'code': -32602, 'message': 'invalid params',
                                  'data': {'httpStatus': 422, 'errors': json.loads(e.json(include_url=False))}}}
        except LogLabCoreException as e:
            response = {'error': {'code': -32000, 'message': str(e), 'data': {'httpStatus': e.httpStatus}}}
        except Exception as e:
            self.core.logger.error('stdio', f"{msg['method']} - internal error - {traceback.format_exc()}")
            response = {'error': {'code': -32603, 'message': f'internal error: {e}'}}

        # requests without id are notifications - no response
        if id is not None:
            self.send({'id': id, **response})
        # stop only after the response to shutdown has been sent
        if msg['method'] == 'shutdown':
            self.stopped.set()

    def __call(self, method, params):
        if not isinstance(params, dict):
            raise RpcError(-32602, 'params must be an object', {'httpStatus': 422})

        if method == 'solve':
            id = self.core.submit(params)
            return self.core.jobs.get(id).toDict()

        if method == 'status':
            job = self.core.jobs.get(self.__jobId(params))
            if job is None:
                raise LogLabCoreException(f"problem id: {params['id']} not found", 400)
            job.lastAccess = time.time()
            return job.toDict()

        if method == 'result':
            content, _, _ = self.core.fetch(self.__jobId(params))
            return content

        if method == 'cancel':
            return self.core.cancel(self.__jobId(params))

        if method in GEO_METHODS:
            return self.core.geo(method, params)

        if method == 'version':
            return {'version': __version__, 'protocol': PROTOCOL_VERSION}

        if method == 'shutdown':
            return {}

        raise RpcError(-32601, f'unknown method {method}')

    def __jobId(self, params):
        id = params.get('id')
        if not isinstance(id, str):
            raise RpcError(-32602, 'params.id is missing', {'httpStatus': 422})
        return id


def main():
    parser = argparse.ArgumentParser(description='local JSON-RPC interface of LogisticsLab (stdin/stdout)')
    parser.add_argument('--logPath', default=paths.logDir(),
                        help='directory for the log files and the matrix cache (default: <project>/logs or LOGLAB_LOG_DIR)')
    parser.add_argument('--osmConfig', default=paths.osmConfigFile(),
                        help='OSM servers (default: confs/logisticsLab.local.yml or confs/logisticsLab.yml)')
    parser.add_argument('--maxProblems', type=int, default=2, help='problems solved at the same time')
    parser.add_argument('--debug', action='store_true', help='debug messages in the log file')
    parser.add_argument('--noMatrixCache', action='store_true',
                        help='without the cache of the OSM matrices (default: matrixCache.sqlite in logPath)')
    args = parser.parse_args()

    # stdout belongs to the protocol - print() and the output of CMPL and the solvers go to stderr
    out = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8', buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr

    os.makedirs(args.logPath, exist_ok=True)
    solverLogFile = os.path.join(args.logPath, 'HiGHS.log')
    conf = {'maxProblems': args.maxProblems,
            'workDir': args.logPath,
            'matrixCache': not args.noMatrixCache,
            'tpp': {'solverLogFile': solverLogFile}}
    logger = CoreLogger(os.path.join(args.logPath, 'logisticsLabLocal.log'), isDebugging=args.debug)

    server = StdioServer(out)
    try:
        server.core = LogisticsLabCore(conf, logger, osmConfigFile=args.osmConfig,
                                       osmLogFile=os.path.join(args.logPath, 'logisticsLab.log'),
                                       onStatusChange=server.notifyStatus)
    except Exception as e:
        logger.error('stdio', f'start failed - {traceback.format_exc()}')
        server.notify('error', {'message': f'start failed: {e}'})
        sys.exit(1)

    logger.info('stdio', f'local interface {__version__} has been started')
    server.notify('ready', {'version': __version__, 'protocol': PROTOCOL_VERSION})

    def readStdin():
        for line in sys.stdin:
            server.handleLine(line)
        server.stopped.set()           # stdin closed - the app has stopped

    threading.Thread(target=readStdin, daemon=True).start()
    server.stopped.wait()

    server.core.shutdown()
    logger.info('stdio', 'local interface has been stopped')
    out.flush()
    os._exit(0)


if __name__ == '__main__':
    multiprocessing.freeze_support()    # needed for PyInstaller on Windows
    main()

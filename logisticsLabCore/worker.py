""" solver process - every problem is solved in a separate process, so that it can be cancelled

    messages from the parent:  (jobId, type, data)  or  None to stop
    messages to the parent:    ('log', level, module, message)
                               ('running', jobId, size)
                               ('done', jobId, {isSolution, objVal, results, size, solvingTime})
                               ('error', jobId, message, httpStatus, size)
"""

from .exception import *
from .items import *
from .tspHandler import *
from .tppHandler import *
from .locationHandlers import *
from .routingHandlers import *
from .flowHandlers import *

import logging
import os
import sys
import time
import traceback


# problem type -> handler; the handler gets the section of the same name from the config
HANDLERS = {
    'tsp': TspHandler,
    'tpp': TppHandler,
    'wlp': WlpHandler,
    'pmedian': PMedianHandler,
    'pcentre': PCentreHandler,
    'scp': ScpHandler,
    'mcp': McpHandler,
    'cpp': CppHandler,
    'vrp': VrpHandler,
    'mincostflow': MinCostFlowHandler,
    'maxflow': MaxFlowHandler,
    'multicommodity': MultiCommodityHandler,
    'multimodal': MultiModalHandler,
}


class PipeLogger:
    """ sends the log messages to the parent - only the parent writes the log file """
    def __init__(self, conn):
        self.__conn = conn

    def __send(self, level, module, message):
        try:
            self.__conn.send(('log', level, module, str(message)))
        except Exception:
            pass

    def info(self, module, message):
        self.__send('info', module, message)

    def warning(self, module, message):
        self.__send('warning', module, message)

    def error(self, module, message):
        self.__send('error', module, message)

    def debug(self, module, message):
        self.__send('debug', module, message)


class PipeLogHandler(logging.Handler):
    """ forwards the log messages of the pyLogisticsLab library as debug messages """
    def __init__(self, logger):
        super().__init__()
        self.__logger = logger

    def emit(self, record):
        self.__logger.debug(record.name, record.getMessage().strip())


def workerMain(conn, conf):
    # own process group - the parent can kill the process together with CMPL and the solvers it has started
    if os.name == 'posix':
        os.setsid()

    # files written by CMPL and the solvers (e.g. HiGHS.log) go to workDir, not to the directory of the app
    if conf.get('workDir'):
        os.makedirs(conf['workDir'], exist_ok=True)
        os.chdir(conf['workDir'])

    logger = PipeLogger(conn)
    libLogger = logging.getLogger('pyLogisticsLab')
    libLogger.setLevel(logging.INFO)
    libLogger.addHandler(PipeLogHandler(logger))

    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            break               # the parent has stopped
        if msg is None:
            break

        jobId, type, data = msg
        size = ''
        try:
            item = PROBLEM_ITEMS[type].model_validate(data)
            handler = HANDLERS[type](item, logger, conf.get(type, {}))
            size = handler.size
            conn.send(('running', jobId, size))

            sTime = time.time()
            handler.solve()
            solvingTime = round(time.time()-sTime, 3)

            conn.send(('done', jobId, {'isSolution': handler.isSolution, 'objVal': handler.objVal,
                                       'results': handler.results, 'size': size, 'solvingTime': solvingTime}))

        except LogLabCoreException as e:
            conn.send(('error', jobId, str(e), e.httpStatus, size))

        except Exception:
            logger.error('worker', f'job {jobId} - {traceback.format_exc()}')
            conn.send(('error', jobId, str(sys.exc_info()[1]), 500, size))

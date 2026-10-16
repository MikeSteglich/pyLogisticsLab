#***********************************************************************
 #  This code is part of pyLogisticsLab
 #
 #  Mike Steglich - Technical University of Applied Sciences
 #  Wildau, Germany
 #
 #  pyLogisticsLab is a project of the Technical University of
 #  Applied Sciences Wildau
 #
 #  pyLogisticsLab is free software; you can redistribute it and/or modify it
 #  under the terms of the GNU Lesser General Public License as published by
 #  the Free Software Foundation; either version 3 of the License, or
 #  (at your option) any later version.
 #
 #  pyLogisticsLab is distributed in the hope that it will be useful, but WITHOUT
 #  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 #  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
 #  License for more details.
 #
 #  You should have received a copy of the GNU Lesser General Public License
 #  along with this program; if not, see <http://www.gnu.org/licenses/>.
 #
 #**********************************************************************

from exception import *
from tspHandler import *
from tppHandler import *
from tools import *
from logger import *

import queue
import threading
import sys
import time
import traceback


# problem type -> handler; the handler gets the section of the same name from the server config
HANDLERS = {
    'tsp': TspHandler,
    'tpp': TppHandler,
}


# status of finished problems - their results are waiting to be fetched by the client
FINISHED = ('solution', 'noSolution', 'error')
# status of problems that occupy the queue or a solver thread
OPEN = ('waiting', 'running')


class Problem:
    def __init__(self, type, data, owner=None):
        self.__type = None
        self.setType(type)
        self.__httpStatus = 200
        self.__status = 'idle'
        self.__results = None
        self.__message = ''
        self.__data = data
        self.owner = owner                 # name of the api key that has submitted the problem
        self.createdTime = time.time()
        self.finishedTime = None


    def setHttpStatus(self,status):
        if not isinstance(status, int):
            self.__httpStatus = 500
        else:
            self.__httpStatus = status

    def getHttpStatus(self):
        return self.__httpStatus
    
    httpStatus = property(getHttpStatus, setHttpStatus)


    def setStatus(self,status):
        if not isinstance(status, str):
            self.__status = 'idle'
        else:
            self.__status = status
        if self.__status in FINISHED:
            self.finishedTime = time.time()

    def getStatus(self):
        return self.__status
    
    status = property(getStatus, setStatus)

    def setResults(self, results):
        if not isinstance(results, dict):
            self.__results = None
        else:
            self.__results=results

    def getResults(self):
        return self.__results
    
    results = property(getResults, setResults)

    def setMessage(self, msg):
        self.__message=str(msg)
    
    def getMessage(self):
        return self.__message
    message = property(getMessage, setMessage)

    def setData(self,data):
        self.__data=data

    def getData(self):
        return self.__data
    
    data = property(getData, setData)

   
    def setType(self, type):
        if not isinstance(type, str):
            raise LogLabServerException(f'wrong type {type}')
        if type.lower() not in HANDLERS:
            raise LogLabServerException(f'wrong type {type}')
        self.__type=type.lower()
    
    def getType(self):
        return self.__type
    
    type = property(getType, setType)


class ProblemQueue:
    def __init__(self, maxProblems, logger, conf):
        self.__problems={}

        self.__logger = logger

        self.__conf=conf

        self.__problemQueue = queue.Queue()

        # protects self.__problems - it is used by the api, the solver threads and the cleanup thread
        self.__lock = threading.Lock()

        for _ in range(maxProblems):
            threading.Thread(target=self.__optimisationWorker, daemon=True).start()

        threading.Thread(target=self.__cleanupWorker, daemon=True).start()

        self.__logger.debug('queue','solver threads have been started')


    def __cleanupWorker(self):
        """ deletes finished problems whose results have not been fetched within maxInactivityTime """
        while True:
            time.sleep(self.__conf['serviceIntervall'])
            self.__cleanup()

    def __cleanup(self):
        limit = time.time() - self.__conf['maxInactivityTime']
        with self.__lock:
            expired = [ id for id, p in self.__problems.items() if p.status in FINISHED and p.finishedTime < limit ]
            for id in expired:
                del self.__problems[id]
        for id in expired:
            self.__logger.info('queue', f'problem {id} - results have not been fetched - deleted')


    def __optimisationWorker(self):
        while True:
            id = self.__problemQueue.get()
            problem = self.getProblem(id)
            if problem is None:
                self.__problemQueue.task_done()
                continue
            type = problem.type
            handler = None

            try:
                self.__logger.debug('queue',f'problem {id} - {type} - running')

                handler=HANDLERS[type](problem.data, self.__logger, self.__conf.get(type, {}))
                problem.status='running'
                problem.message='Problem is running'

                sTime=time.time()
                handler.solve()
                solvingTime=round(time.time()-sTime, 3)

                if handler.isSolution:
                    problem.httpStatus=200
                    problem.results={'objVal': handler.objVal, 'solvingTime': solvingTime, **handler.results}
                    problem.message='Solution has been found'
                    problem.status='solution'
                    self.__logger.info('queue', f'problem {id} - {type} - {handler.size} - solution - objVal {handler.objVal} - {solvingTime}s')
                else:
                    problem.httpStatus=404
                    problem.message='No solution has been found'
                    problem.status='noSolution'
                    self.__logger.info('queue', f'problem {id} - {type} - {handler.size} - noSolution - {solvingTime}s')

            except LogLabServerException as e:
                problem.httpStatus=400
                problem.status='error'
                problem.message=e
                size = f' - {handler.size}' if handler else ''
                self.__logger.error('queue', f'problem {id} - {type}{size} - {e}')

            except:
                problem.httpStatus=500
                problem.status='error'
                problem.message=str(sys.exc_info()[1])
                self.__logger.error('queue', f'problem {id} - {type} - internal error - {traceback.format_exc()}')

            finally:
                self.__problemQueue.task_done()


    def addProblem(self, type, data, owner=None, maxOpenProblems=None):
        """ adds a problem to the queue - raises LogLabLimitException if the queue or the owner has too many open problems """
        with self.__lock:
            openProblems = [ p for p in self.__problems.values() if p.status in OPEN ]

            if len(openProblems) >= self.__conf['maxQueueSize']:
                raise LogLabLimitException(f'server is busy - too many problems in queue, please try again later', 503)

            if maxOpenProblems is not None and sum(1 for p in openProblems if p.owner == owner) >= maxOpenProblems:
                raise LogLabLimitException(f'too many open problems - maximum is {maxOpenProblems}, please fetch the results first', 429)

            id = sessionId(self.__problems)
            problem = Problem(type, data, owner)
            problem.status='waiting'
            problem.message='Problem is waiting in queue'
            self.__problems[id] = problem

        self.__problemQueue.put(id)
        return id

    def getProblem(self, id):
        """ returns the problem or None """
        with self.__lock:
            return self.__problems.get(id)

    def delProblem(self, id):
        with self.__lock:
            self.__problems.pop(id, None)


    def getProblems(self):
        return self.__problems
    problems = property(getProblems)  


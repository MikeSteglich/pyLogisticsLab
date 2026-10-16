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
from config import *
from logger import *
from items import *
from problemQueue import *
from matrixHandler import *
from routeHandler import *
from geoCodingHandler import *

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

import sys
import traceback

app = FastAPI()


conf = Config().conf
logger = Logging(logfile=conf['logFile'], isLogging=conf['logging'], isDebugging=conf['debugging'],
                 maxBytes=conf['logMaxBytes'], backupCount=conf['logBackupCount'])
version='v1'

problemQueue=ProblemQueue(conf['maxProblems'],logger, conf)

logger.info('main','Server has been started')


#*************** invalid requests ******************************

@app.exception_handler(RequestValidationError)
async def validationErrorHandler(request: Request, exc: RequestValidationError):
    """ logs requests rejected by pydantic (422) - the response is the FastAPI default """
    errors = '; '.join( f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors() )
    logger.warning('main', f'invalid request {request.url.path} - {errors}')
    return await request_validation_exception_handler(request, exc)


#*************** optimisation problems *************************

def submitProblem(type, item):
    """ adds a problem to the queue - the results are requested via /results """
    id = problemQueue.addProblem(type, item)
    problem = problemQueue.problems[id]
    logger.info('main', f'problem {id} - {type} - received by server')
    return JSONResponse(content={'id': id,  'status': problem.status, 'message': problem.message}, status_code=problem.httpStatus)


@app.post(f'/{version}/solve')
async def solveApi(problemItem: ProblemItem):
    return submitProblem(problemItem.type, problemItem)


@app.post(f'/{version}/tsp')
async def tspApi(tspItem: TspItem):
    return submitProblem('tsp', tspItem)


@app.post(f'/{version}/tpp')
async def tppApi(tppItem: TppItem):
    return submitProblem('tpp', tppItem)


@app.post(f'/{version}/results')
async def resultsApi(resultItem: ResultItem):
    id = resultItem.id
    if not id in problemQueue.problems:
        httpStatus=400
        message=f'problem id: {id} not found'
        ret = JSONResponse(content={'id': id, 'status': 'error', 'message': message}, status_code=httpStatus)
        logger.warning('main', f'problem {id} does not exist')
    else:
        problem = problemQueue.problems[id]
        httpStatus=problem.httpStatus
        message=problem.message
        status = problem.status
        type = problem.type
        if httpStatus==200:
            if status=='solution':
                ret = JSONResponse(content={'id': id, 'status': status, 'message': message, 'results': problem.results}, status_code=httpStatus)
                problemQueue.delProblem(id)
            else:
                ret = JSONResponse(content={'id': id, 'status': status, 'message': message}, status_code=httpStatus)

        else:
            ret = JSONResponse(content={'id': id, 'status': status, 'message': message}, status_code=httpStatus)
            problemQueue.delProblem(id)

        # polling while waiting or running is only logged in debug mode
        if status in ('waiting', 'running'):
            logger.debug('main', f'problem {id} - {type} - {status} - status sent to client')
        else:
            logger.info('main', f'problem {id} - {type} - {status} - results sent to client')
    return ret


#*************** geo services **********************************

def geoErrorResponse(name, httpStatus, message):
    logger.error('main', f'{name} request - {httpStatus} - {message}')
    return JSONResponse(content={'status': 'error', 'message': message}, status_code=httpStatus)

def geoRequest(name, createHandler, content):
    """ creates the handler and sends its results via content(handler) or an error to the client """
    logger.info('main', f'{name} request')
    try:
        h=createHandler()
    except LogLabServerException as e:
        return geoErrorResponse(name, 400, str(e))
    except:
        logger.error('main', f'{name} request - internal error - {traceback.format_exc()}')
        return JSONResponse(content={'status': 'error', 'message': str(sys.exc_info()[1])}, status_code=500)

    if h.status=='ok':
        logger.info('main', f'{name} request - {h.status} - {h.message} - results sent to client')
        return JSONResponse(content={'status': h.status, 'message': h.message, **content(h)}, status_code=h.httpStatus)
    return geoErrorResponse(name, h.httpStatus, h.message)


@app.post(f'/{version}/matrix')
async def matrixApi(matrixItem: MatrixItem):
    def content(m):
        if matrixItem.matrixMode=='distances':
            return {'distances': m.distances}
        elif matrixItem.matrixMode=='durations':
            return {'durations': m.durations}
        return {'distances': m.distances, 'durations': m.durations}
    return geoRequest('Matrix', lambda: MatrixHandler(matrixItem,logger), content)


@app.post(f'/{version}/routing')
async def routingApi(routeItem: RouteItem):
    return geoRequest('Routing', lambda: RouteHandler(routeItem,logger), lambda r: {'route': r.route})


@app.post(f'/{version}/coordinates')
async def coordinatesApi(coordinatesItem: SearchCoordinatesItem):
    return geoRequest('Coordinates', lambda: GeoCodingHandler(coordinatesItem,logger,'coordinates'), lambda g: {'coordinates': g.results})


@app.post(f'/{version}/search')
async def searchApi(searchItem: SearchItem):
    return geoRequest('Search', lambda: GeoCodingHandler(searchItem,logger,'search'), lambda g: {'results': g.results})


@app.post(f'/{version}/reverse')
async def reverseApi(reverseItem: ReverseItem):
    return geoRequest('Reverse', lambda: GeoCodingHandler(reverseItem,logger,'reverse'), lambda g: {'results': g.results})

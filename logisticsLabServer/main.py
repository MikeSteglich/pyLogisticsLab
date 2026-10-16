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
from apiKeys import *

from fastapi import FastAPI, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

import sys
import traceback


conf = Config().conf
logger = Logging(logfile=conf['logFile'], isLogging=conf['logging'], isDebugging=conf['debugging'],
                 maxBytes=conf['logMaxBytes'], backupCount=conf['logBackupCount'])
version='v1'

# /docs, /redoc and /openapi.json only if enabled in the config
if conf['docs']:
    app = FastAPI()
else:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

problemQueue=ProblemQueue(conf['maxProblems'],logger, conf)

if conf['authentication']:
    keyStore = ApiKeyStore(conf['apiKeyFile'], logger, conf['maxOpenProblemsPerKey'])
else:
    keyStore = None
    logger.warning('main', 'authentication is disabled - the server is open for everyone')

logger.info('main','Server has been started')


#*************** authentication ********************************

apiKeyHeader = APIKeyHeader(name='X-API-Key', auto_error=False)

# used for all requests if authentication is disabled
anonymousKey = ApiKey({'name': 'anonymous', 'hash': '-'}, conf['maxOpenProblemsPerKey'])

def authenticate(key):
    if keyStore is None:
        return anonymousKey
    if not key:
        raise LogLabLimitException('api key is missing (header X-API-Key)', 401)
    apiKey = keyStore.lookup(key)
    if apiKey is None:
        raise LogLabLimitException('invalid api key', 401)
    if not apiKey.isValid():
        raise LogLabLimitException(f'api key {apiKey.name} is expired or disabled', 401)
    return apiKey

def checkAllowed(apiKey, service):
    if not apiKey.isAllowed(service):
        raise LogLabLimitException(f'api key {apiKey.name} is not allowed to use {service}', 403)

def requireService(service=None):
    """ dependency: checks the api key and the right to use the service, returns the ApiKey """
    async def check(key: str = Security(apiKeyHeader)):
        apiKey = authenticate(key)
        if service:
            checkAllowed(apiKey, service)
        return apiKey
    return check


#*************** rejected requests *****************************

@app.exception_handler(LogLabLimitException)
async def limitErrorHandler(request: Request, exc: LogLabLimitException):
    """ missing rights and limits (401, 403, 429, 503) """
    logger.warning('main', f'request {request.url.path} rejected - {exc.httpStatus} - {exc}')
    return JSONResponse(content={'status': 'error', 'message': str(exc)}, status_code=exc.httpStatus)

@app.exception_handler(RequestValidationError)
async def validationErrorHandler(request: Request, exc: RequestValidationError):
    """ logs requests rejected by pydantic (422) - the response is the FastAPI default """
    errors = '; '.join( f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors() )
    logger.warning('main', f'invalid request {request.url.path} - {errors}')
    return await request_validation_exception_handler(request, exc)


#*************** optimisation problems *************************

def submitProblem(type, item, apiKey):
    """ adds a problem to the queue - the results are requested via /results """
    id = problemQueue.addProblem(type, item, owner=apiKey.name, maxOpenProblems=apiKey.maxOpenProblems)
    problem = problemQueue.getProblem(id)
    logger.info('main', f'problem {id} - {type} - received by server - key {apiKey.name}')
    return JSONResponse(content={'id': id,  'status': problem.status, 'message': problem.message}, status_code=problem.httpStatus)


@app.post(f'/{version}/solve')
async def solveApi(problemItem: ProblemItem, apiKey: ApiKey = Security(requireService())):
    checkAllowed(apiKey, problemItem.type)
    return submitProblem(problemItem.type, problemItem, apiKey)


@app.post(f'/{version}/tsp')
async def tspApi(tspItem: TspItem, apiKey: ApiKey = Security(requireService('tsp'))):
    return submitProblem('tsp', tspItem, apiKey)


@app.post(f'/{version}/tpp')
async def tppApi(tppItem: TppItem, apiKey: ApiKey = Security(requireService('tpp'))):
    return submitProblem('tpp', tppItem, apiKey)


@app.post(f'/{version}/results')
async def resultsApi(resultItem: ResultItem, apiKey: ApiKey = Security(requireService())):
    id = resultItem.id
    problem = problemQueue.getProblem(id)

    # results can only be fetched with the key that has submitted the problem
    if problem is None or problem.owner != apiKey.name:
        httpStatus=400
        message=f'problem id: {id} not found'
        ret = JSONResponse(content={'id': id, 'status': 'error', 'message': message}, status_code=httpStatus)
        if problem is None:
            logger.warning('main', f'problem {id} does not exist - key {apiKey.name}')
        else:
            logger.warning('main', f'problem {id} belongs to key {problem.owner} - requested by key {apiKey.name}')
    else:
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

def geoRequest(name, createHandler, content, apiKey):
    """ creates the handler and sends its results via content(handler) or an error to the client """
    logger.info('main', f'{name} request - key {apiKey.name}')
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
async def matrixApi(matrixItem: MatrixItem, apiKey: ApiKey = Security(requireService('matrix'))):
    def content(m):
        if matrixItem.matrixMode=='distances':
            return {'distances': m.distances}
        elif matrixItem.matrixMode=='durations':
            return {'durations': m.durations}
        return {'distances': m.distances, 'durations': m.durations}
    return geoRequest('Matrix', lambda: MatrixHandler(matrixItem,logger), content, apiKey)


@app.post(f'/{version}/routing')
async def routingApi(routeItem: RouteItem, apiKey: ApiKey = Security(requireService('routing'))):
    return geoRequest('Routing', lambda: RouteHandler(routeItem,logger), lambda r: {'route': r.route}, apiKey)


@app.post(f'/{version}/coordinates')
async def coordinatesApi(coordinatesItem: SearchCoordinatesItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Coordinates', lambda: GeoCodingHandler(coordinatesItem,logger,'coordinates'), lambda g: {'coordinates': g.results}, apiKey)


@app.post(f'/{version}/search')
async def searchApi(searchItem: SearchItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Search', lambda: GeoCodingHandler(searchItem,logger,'search'), lambda g: {'results': g.results}, apiKey)


@app.post(f'/{version}/reverse')
async def reverseApi(reverseItem: ReverseItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Reverse', lambda: GeoCodingHandler(reverseItem,logger,'reverse'), lambda g: {'results': g.results}, apiKey)

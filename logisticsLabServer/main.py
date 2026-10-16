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
from apiKeys import *
from logisticsLabCore import *

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

core = LogisticsLabCore(conf, logger, osmConfigFile=conf['osmConfigFile'], osmLogFile=conf['osmLogFile'])

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

def submitProblem(item, apiKey):
    """ adds a problem to the queue - the results are requested via /results """
    id = core.submit(item, owner=apiKey.name, maxOpenProblems=apiKey.maxOpenProblems)
    job = core.jobs.get(id)
    logger.info('main', f'problem {id} - {item.type} - received by server - key {apiKey.name}')
    return JSONResponse(content=job.toDict(), status_code=job.httpStatus)


@app.post(f'/{version}/solve')
async def solveApi(problemItem: ProblemItem, apiKey: ApiKey = Security(requireService())):
    checkAllowed(apiKey, problemItem.type)
    return submitProblem(problemItem, apiKey)


@app.post(f'/{version}/tsp')
async def tspApi(tspItem: TspItem, apiKey: ApiKey = Security(requireService('tsp'))):
    return submitProblem(tspItem, apiKey)


@app.post(f'/{version}/tpp')
async def tppApi(tppItem: TppItem, apiKey: ApiKey = Security(requireService('tpp'))):
    return submitProblem(tppItem, apiKey)


@app.post(f'/{version}/results')
async def resultsApi(resultItem: ResultItem, apiKey: ApiKey = Security(requireService())):
    """ status of a problem and its results if it is finished - finished problems are deleted afterwards """
    id = resultItem.id
    try:
        # results can only be fetched with the key that has submitted the problem
        content, httpStatus, job = core.fetch(id, owner=apiKey.name)
    except LogLabCoreException as e:
        job = core.jobs.get(id)
        if job is None:
            logger.warning('main', f'problem {id} does not exist - key {apiKey.name}')
        else:
            logger.warning('main', f'problem {id} belongs to key {job.owner} - requested by key {apiKey.name}')
        return JSONResponse(content={'id': id, 'status': 'error', 'message': str(e)}, status_code=e.httpStatus)

    # polling while waiting or running is only logged in debug mode
    if job.status in OPEN:
        logger.debug('main', f'problem {id} - {job.type} - {job.status} - status sent to client')
    else:
        logger.info('main', f'problem {id} - {job.type} - {job.status} - results sent to client')
    return JSONResponse(content=content, status_code=httpStatus)


@app.post(f'/{version}/cancel')
async def cancelApi(resultItem: ResultItem, apiKey: ApiKey = Security(requireService())):
    """ cancels a waiting or running problem - the status changes to cancelled """
    id = resultItem.id
    try:
        content = core.cancel(id, owner=apiKey.name)
    except LogLabCoreException as e:
        logger.warning('main', f'cancel - problem {id} not found - key {apiKey.name}')
        return JSONResponse(content={'id': id, 'status': 'error', 'message': str(e)}, status_code=e.httpStatus)
    logger.info('main', f'problem {id} - cancel requested - key {apiKey.name}')
    return JSONResponse(content=content, status_code=200)


#*************** geo services **********************************

def geoRequest(name, service, item, apiKey):
    """ geo service of the core - sends its results or an error to the client """
    logger.info('main', f'{name} request - key {apiKey.name}')
    try:
        content = core.geo(service, item)
    except LogLabCoreException as e:
        logger.error('main', f'{name} request - {e.httpStatus} - {e}')
        return JSONResponse(content={'status': 'error', 'message': str(e)}, status_code=e.httpStatus)
    except:
        logger.error('main', f'{name} request - internal error - {traceback.format_exc()}')
        return JSONResponse(content={'status': 'error', 'message': str(sys.exc_info()[1])}, status_code=500)

    logger.info('main', f"{name} request - ok - {content['message']} - results sent to client")
    return JSONResponse(content={'status': 'ok', **content}, status_code=200)


@app.post(f'/{version}/matrix')
async def matrixApi(matrixItem: MatrixItem, apiKey: ApiKey = Security(requireService('matrix'))):
    return geoRequest('Matrix', 'matrix', matrixItem, apiKey)


@app.post(f'/{version}/routing')
async def routingApi(routeItem: RouteItem, apiKey: ApiKey = Security(requireService('routing'))):
    return geoRequest('Routing', 'routing', routeItem, apiKey)


@app.post(f'/{version}/coordinates')
async def coordinatesApi(coordinatesItem: SearchCoordinatesItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Coordinates', 'coordinates', coordinatesItem, apiKey)


@app.post(f'/{version}/search')
async def searchApi(searchItem: SearchItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Search', 'search', searchItem, apiKey)


@app.post(f'/{version}/reverse')
async def reverseApi(reverseItem: ReverseItem, apiKey: ApiKey = Security(requireService('geocoding'))):
    return geoRequest('Reverse', 'reverse', reverseItem, apiKey)

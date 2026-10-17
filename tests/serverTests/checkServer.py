""" regression test of the server - solves the problems of the find*Server.py scripts and checks the results

    Every answer is also checked against the result models of logisticsLabCore/results.py (JSON Schema of the app).

    ./runServerTests.sh             creates the test keys, starts a local server if necessary and runs this test

    or with an own server - the settings come from the environment or from .env (python createTestKeys.py):
    LOGLAB_API_KEY=...                      key for all services
    LOGLAB_API_KEY_RESTRICTED=...           optional - key without the service contpcentre (e.g. --allowed tsp)
    LOGLAB_URL=http://127.0.0.1:8000/v1/    default: local server
    python checkServer.py
"""

from logLabClient import solve, solveWithStatus

import importlib
import os
import sys

# result models of the core - the project directory is two levels up
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from logisticsLabCore.results import RESULT_ITEMS, ProblemAnswer


# script -> expected objective values of its payloads
# the heuristics (vrp, contpmedian, contpcentre) may find better solutions, but never worse ones
EXPECTED = {
    'findWlpServer':            [14100],
    'findPMedianServer':        [33],
    'findPCentreServer':        [3],
    'findScpServer':            [2],
    'findMcpServer':            [10],
    'findCppServer':            [26],
    'findVrpServer':            [28],
    'findMinCostFlowServer':    [114],
    'findMaxFlowServer':        [15],
    'findMultiCommodityServer': [62],
    'findMultiModalServer':     [90],
    'findContPMedianServer':    [4968.608, 6039.286],
    'findContPCentreServer':    [42.566, 56.541],
}
# problems without an own find*Server.py script that uses logLabClient: endpoint -> (payloads, expected)
INLINE = {
    'tsp': ([{"distances": [[0, 4, 7, 5, 6], [4, 0, 3, 6, 8], [7, 3, 0, 4, 7], [5, 6, 4, 0, 3], [6, 8, 7, 3, 0]]}], [20]),
    'tpp': ([{"varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]], "supplies": [5000, 6000, 2500],
              "demands": [6000, 4000, 2000, 1500]}], [39500]),
}
HEURISTICS = ['vrp', 'contpmedian', 'contpcentre']
MAXIMIZE = ['mcp', 'maxflow']

nrOfErrors = 0


def check(name, isOk, info=''):
    global nrOfErrors
    if not isOk:
        nrOfErrors += 1
    print(f"{'ok    ' if isOk else 'FAILED'} {name} {info}")


def checkObjVal(name, endpoint, ret, expected):
    if ret.get('status') != 'solution':
        check(name, False, f'- no solution: {ret}')
        return
    objVal = ret['results']['objVal']
    tol = 1e-3 * max(1, abs(expected))
    if endpoint in HEURISTICS:
        isOk = objVal >= expected - tol if endpoint in MAXIMIZE else objVal <= expected + tol
    else:
        isOk = abs(objVal - expected) <= tol
    check(name, isOk, f'- objVal {objVal}, expected {expected}')


def checkSchema(name, endpoint, ret):
    """ the answer and its results match the models of the JSON Schema - unknown fields are errors """
    try:
        ProblemAnswer.model_validate(ret)
        if ret.get('status') == 'solution':
            RESULT_ITEMS[endpoint].model_validate(ret['results'])
        check(f'{name} schema', True, f'- {RESULT_ITEMS[endpoint].__name__}')
    except Exception as e:
        check(f'{name} schema', False, f'- {str(e)[:300]}')


def checkError(name, endpoint, payload, status, apiKey=None):
    """ submits a wrong problem - status: expected http status of the request (422, 403) or of the results (400, 404) """
    code, ret = solveWithStatus(endpoint, payload, verbose=False, apiKey=apiKey)
    check(name, code == status, f'- {code}, expected {status}: {str(ret.get("message", ret))[:90]}')


#*************** problems ************************************************
print('== problems')
problems = [ (endpoint, payloads, expected) for endpoint, (payloads, expected) in INLINE.items() ]
for script, expected in EXPECTED.items():
    module = importlib.import_module(script)
    problems.append((module.endpoint, module.payloads, expected))

for endpoint, payloads, expected in problems:
    if len(payloads) != len(expected):
        check(endpoint, False, f'- {len(payloads)} payloads, {len(expected)} expected values')
        continue
    for k, (payload, exp) in enumerate(zip(payloads, expected)):
        name = f'{endpoint}[{k}]'
        ret = solve(endpoint, payload, verbose=False)
        checkObjVal(name, endpoint, ret, exp)
        checkSchema(name, endpoint, ret)

        # the generic endpoint gives the same result
        ret2 = solve('solve', {"type": endpoint, **payload}, verbose=False)
        if endpoint not in HEURISTICS:
            check(f'{name} via /solve', ret2.get('results', {}).get('objVal') == ret.get('results', {}).get('objVal'))
        else:
            checkObjVal(f'{name} via /solve', endpoint, ret2, exp)


#*************** errors ************************************************
print('== errors')
flow = importlib.import_module('findMinCostFlowServer').payloads[0]
cont = importlib.import_module('findContPMedianServer').payloads[0]

checkError('mincostflow unbalanced', 'mincostflow', {**flow, "demands": [0, 0, 5, 14]}, 400)
checkError('mincostflow capacity too small', 'mincostflow', {**flow, "maxCaps": [1, 1, 1, 1, 1]}, 404)
checkError('maxflow unbounded', 'maxflow', {"edges": flow["edges"], "source": 0, "sink": 3, "maxCaps": ["M"] * 5}, 400)
checkError('maxflow missing field', 'maxflow', {"edges": flow["edges"], "source": 0, "sink": 3}, 422)
checkError('contpmedian capacity too small', 'contpmedian', {**cont, "capacities": 10}, 400)
checkError('contpmedian p too large', 'contpmedian', {**cont, "p": len(cont["coordinates"]) + 1}, 400)
checkError('contpcentre two hemispheres', 'contpcentre', {"p": 1, "coordinates": [[0, 0], [0, 120], [0, -120]]}, 400)
checkError('unknown field', 'contpcentre', {**cont, "radius": 3}, 422)

restricted = os.environ.get('LOGLAB_API_KEY_RESTRICTED')
if restricted:
    checkError('key without the service', 'contpcentre', cont, 403, apiKey=restricted)
else:
    print('skip   key without the service - LOGLAB_API_KEY_RESTRICTED is not set')


print(f'== {nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

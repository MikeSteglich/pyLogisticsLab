""" regression test of the server - solves the problems of the find*Server.py scripts and checks the results

    Every answer is also checked against the result models of logisticsLabCore/results.py (JSON Schema of the app).

    ./runServerTests.sh             creates the test keys, starts a local server if necessary and runs this test

    or with an own server - the settings come from the environment or from .env (python createTestKeys.py):
    LOGLAB_API_KEY=...                      key for all services
    LOGLAB_API_KEY_RESTRICTED=...           optional - key without the service contpcentre (e.g. --allowed tsp)
    LOGLAB_URL=http://127.0.0.1:8000/v1/    default: local server
    python checkServer.py
"""

from logLabClient import solve, solveWithStatus, request

import importlib
import math
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
    'findMinCostFlowServer':    [114, 180],
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


#*************** geo services ************************************************
# they need the OSM servers of logisticsLab.yml - if these are not available, the checks are skipped

def checkGeo(name, endpoint, payload, test, status=200, apiKey=None):
    """ synchronous geo request - test(answer) checks the content of a successful answer """
    try:
        code, ret = request(endpoint, payload, apiKey=apiKey)
    except Exception as e:
        check(name, False, f'- {e}')
        return
    isOk = code == status and (status != 200 or (ret.get('status') == 'ok' and test(ret)))
    check(name, isOk, f'- {code}, expected {status}: {str(ret.get("message", ret))[:90]}')

def isMatrix(m, rows, cols):
    return isinstance(m, list) and len(m) == rows and all(isinstance(r, list) and len(r) == cols for r in m)

def inGermany(c):
    return 47 < c[0] < 56 and 5 < c[1] < 16

def haversine(a, b):
    """ great-circle distance in m """
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1) * math.cos(la2) * math.sin((lo2-lo1)/2)**2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))

print('== geo services')
matrix = importlib.import_module('getMatrixServer').payloads
route = importlib.import_module('getRouteServer').payloads
n = len(matrix[0]['coordinates'])

code, ret = request('matrix', matrix[0])
if code >= 500:
    print(f'skip   geo services - OSM servers not available: {code} {str(ret.get("message", ret))[:90]}')
else:
    checkGeo('matrix both', 'matrix', matrix[0],
             lambda r: isMatrix(r['distances'], n, n) and isMatrix(r['durations'], n, n)
                       and all(r['distances'][i][i] == 0 for i in range(n)))
    checkGeo('matrix sources x destinations', 'matrix', matrix[1], lambda r: isMatrix(r['distances'], 2, 2))
    for k, payload in enumerate(route):
        checkGeo(f'routing[{k}]', 'routing', payload, lambda r: len(r['route']) >= 2 and all(inGermany(c) for c in r['route']))
    checkGeo('coordinates', 'coordinates', importlib.import_module('getGeoCodingCoords').payloads[0],
             lambda r: len(r['coordinates']) == 3 and all(inGermany(c) for c in r['coordinates']))
    checkGeo('coordinates not found', 'coordinates', {"adresses": ["Klosterfelde", "Xyzqwv Nirgendwo 999"]},
             lambda r: r['coordinates'][1] is None and r['hits'][1] == [] and inGermany(r['coordinates'][0]))
    checkGeo('coordinates limit', 'coordinates', {"adresses": ["Klosterfelde"], "limit": 3},
             lambda r: 1 <= len(r['hits'][0]) <= 3 and all({'coordinates', 'name', 'city', 'postcode', 'countrycode', 'server'}
                                                         <= set(h) for h in r['hits'][0])
                       and r['coordinates'][0] == r['hits'][0][0]['coordinates'])
    checkGeo('coordinates countrycodes', 'coordinates', {"adresses": ["Klosterfelde"], "limit": 3, "countrycodes": ["DE"]},
             lambda r: all(h['countrycode'].upper() == 'DE' for h in r['hits'][0]))
    checkGeo('coordinates near', 'coordinates', {"adresses": ["Hauptstraße 1"], "limit": 2, "near": [52.32, 13.63]},
             lambda r: r['coordinates'][0] is not None and haversine(r['coordinates'][0], [52.32, 13.63]) < 30000)
    checkGeo('coordinates limit 11', 'coordinates', {"adresses": ["Klosterfelde"], "limit": 11}, None, status=422)
    checkGeo('search not found', 'search', {"adress": "Xyzqwv Nirgendwo 999"}, lambda r: r['results'] == [])
    checkGeo('search', 'search', importlib.import_module('getGeoCodingSearch').payloads[0], lambda r: len(r['results']) > 0)
    checkGeo('reverse', 'reverse', importlib.import_module('getGeoCodingReverse').payloads[0],
             lambda r: r['results'] and 'name' in r['results'][0])

    # a problem whose matrix is calculated from coordinates - the matrix is part of the results
    tspCoords = matrix[0]['coordinates']
    ret = solve('tsp', {"coordinates": tspCoords}, verbose=False)
    check('tsp from coordinates', ret.get('status') == 'solution' and sorted(ret['results']['route'][:-1]) == list(range(n)),
          f"- {ret.get('status')}: {ret.get('results', {}).get('route', ret.get('message'))}")
    checkSchema('tsp from coordinates', 'tsp', ret)

    checkGeo('matrix wrong coordinate', 'matrix', {"coordinates": [[95, 13.4], [52.5, 13.4]]}, None, status=400)
    checkGeo('routing unknown travelmode', 'routing', {**route[0], "travelmode": "plane"}, None, status=422)

    # cache of the OSM matrices - the same request again comes from the cache, noCache loads it again
    coords = matrix[0]['coordinates']
    request('matrix', {"coordinates": coords})
    checkGeo('matrix cache', 'matrix', {"coordinates": coords}, lambda r: r['matrixInfo']['source'] == 'cache')
    checkGeo('matrix noCache', 'matrix', {"coordinates": coords, "noCache": True}, lambda r: r['matrixInfo']['source'] == 'osm')

    # costs: km x costPerKm + h x timeFactor x costPerHour, the durations include the timeFactor
    costs = {"coordinates": coords, "matrixMode": "all", "costPerKm": 0.5, "costPerHour": 30, "timeFactor": 1.2}
    checkGeo('matrix costs', 'matrix', costs,
             lambda r: all(abs(r['costs'][i][j] - (r['distances'][i][j] / 1000 * 0.5 + r['durations'][i][j] / 3600 * 30)) < 1e-6
                           for i in range(n) for j in range(n)) and r['matrixInfo']['costPerHour'] == 30)

    # vrp from coordinates with maxTime: distances and times of the same raw data
    ret = solve('vrp', {"coordinates": coords, "demands": [0, 1, 1, 1], "capacities": [5], "maxTime": 100000,
                        "maxSolvingTime": 2}, verbose=False)
    check('vrp distances and times from coordinates', ret.get('status') == 'solution'
          and ret['results']['matrixInfo']['matrices'] == ['distances', 'times'] and 'times' in ret['results'],
          f"- {ret.get('status')}: {ret.get('results', {}).get('matrixInfo', ret.get('message'))}")
    checkSchema('vrp from coordinates', 'vrp', ret)


# bee line matrices need no OSM servers
coords = matrix[0]['coordinates']
beeLine = {"coordinates": coords, "matrixSource": "beeline", "detourFactor": 1.25, "averageSpeed": 40, "matrixMode": "both"}
checkGeo('matrix beeline', 'matrix', beeLine,
         lambda r: r['matrixInfo']['source'] == 'beeline'
                   and all(abs(r['distances'][i][j] - haversine(coords[i], coords[j]) * 1.25) < 1e-6 for i in range(n) for j in range(n))
                   and all(abs(r['durations'][i][j] - r['distances'][i][j] / (40 / 3.6)) < 1e-6 for i in range(n) for j in range(n)))

# transportation problem with a cost matrix from coordinates
tppCosts = {"sourceCoordinates": coords[:2], "destinationCoordinates": coords[2:], "supplies": [10, 10], "demands": [8, 8],
            "matrixSource": "beeline", "matrixMode": "costs", "costPerKm": 1.5}
ret = solve('tpp', tppCosts, verbose=False)
check('tpp with costs from coordinates', ret.get('status') == 'solution'
      and ret['results']['matrixInfo']['matrices'] == ['costs'] and ret['results']['varCosts'][0][0] > 0,
      f"- {ret.get('status')}: {ret.get('results', {}).get('varCosts', ret.get('message'))}")
checkSchema('tpp with costs from coordinates', 'tpp', ret)
checkError('tpp costs without cost rates', 'tpp', {**tppCosts, "costPerKm": None}, 400)
checkGeo('matrix detourFactor 0', 'matrix', {**beeLine, "detourFactor": 0}, None, status=422)

checkGeo('matrix missing field', 'matrix', {"travelmode": "car"}, None, status=422)
if restricted:
    checkGeo('key without the service matrix', 'matrix', matrix[0], None, status=403, apiKey=restricted)


print(f'== {nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

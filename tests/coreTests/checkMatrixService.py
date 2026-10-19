""" test of the matrix service (logisticsLabCore/matrixService.py) without OSM servers

    python tests/coreTests/checkMatrixService.py      (project directory in PYTHONPATH)

    osm.Matrix and the data state of the ORS servers are replaced by fakes - an update of the servers is simulated
    by another graph_build_date. At the end the data state of the configured servers is read, if they are available.
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from logisticsLabCore import matrixService as ms
from logisticsLabCore.items import MatrixItem
from logisticsLabCore.exception import LogLabCoreException


nrOfErrors = 0

def check(name, isOk, info=''):
    global nrOfErrors
    if not isOk:
        nrOfErrors += 1
    print(f"{'ok    ' if isOk else 'FAILED'} {name} {info}")


#*************** fakes ************************************************
loads = []          # every load from the "OSM servers"

class FakeMatrix:
    """ distances 1000 m x |i - j|, durations 60 s x |i - j| """
    def __init__(self, coords, sources=None, destinations=None):
        self.__s, self.__d = sources, destinations
    def loadMatrix(self, travelmode='car'):
        loads.append(travelmode)
        return 200, 'OK'
    distanceMatrix = property(lambda self: [ [ 1000.0 * abs(i - j) for j in self.__d ] for i in self.__s ])
    timeMatrix = property(lambda self: [ [ 60.0 * abs(i - j) for j in self.__d ] for i in self.__s ])
    matrixStatus = 'exact'
    fillFactors = None

version = {'graphDate': '2025-01-10T22:22:50Z', 'osmDate': '2024-12-30T00:59:58Z'}
realLoadVersion = ms._loadVersion
ms.osm.Matrix = FakeMatrix
ms._loadVersion = lambda travelmode: version


def fresh(maxAgeDays=180):
    """ new cache file, empty process memory, data state checked again """
    fileName = os.path.join(tempfile.mkdtemp(), 'matrixCache.sqlite')
    ms.configure({'matrixCache': True, 'matrixCacheFile': fileName, 'matrixCacheMaxAge': maxAgeDays})
    ms._recent.clear()
    ms._versions.clear()
    loads.clear()

def restart():
    """ a new process: the SQLite file stays, the memory of the process is empty """
    ms._recent.clear()
    ms._versions.clear()


coords = [[52.52, 13.40], [52.39, 13.06], [52.41, 12.55], [52.34, 14.55]]
options = MatrixItem(coordinates=coords, costPerKm=0.5, costPerHour=30, timeFactor=1.2)


#*************** cache ************************************************
print('== cache')
fresh()
_, info = ms.matrix(coords, options, 'distances')
check('first request from the OSM servers', info['source'] == 'osm' and len(loads) == 1, info)
check('osmDate in matrixInfo', info.get('osmDate') == version['osmDate'])
_, info = ms.matrix(coords, options, 'times')
check('times of the same raw data without a new load', info['source'] == 'cache' and len(loads) == 1)
restart()
_, info = ms.matrix(coords, options, 'costs')
check('after a restart from the SQLite file', info['source'] == 'cache' and len(loads) == 1)

d, _ = ms.matrix(coords, options, 'distances', rounded=False)
t, _ = ms.matrix(coords, options, 'times', rounded=False)
c, _ = ms.matrix(coords, options, 'costs', rounded=False)
check('times x timeFactor', t[0][3] == 180 * 1.2)
check('costs = km x costPerKm + h x costPerHour', abs(c[0][3] - (3 * 0.5 + 216 / 3600 * 30)) < 1e-9)
d[0][1] = -1
check('changed results do not change the cache', ms.matrix(coords, options, 'distances', rounded=False)[0][0][1] == 1000)

_, info = ms.matrix(coords, MatrixItem(coordinates=coords, noCache=True), 'distances')
check('noCache loads again', info['source'] == 'osm' and len(loads) == 2)
_, info = ms.matrix(coords[:3], options, 'distances')
check('other coordinates are another entry', info['source'] == 'osm' and len(loads) == 3)


#*************** data state ************************************************
print('== data state of the ORS servers')
restart()
version = {'graphDate': '2025-04-01T03:00:00Z', 'osmDate': '2025-03-28T00:00:00Z'}
_, info = ms.matrix(coords, options, 'distances')
check('update of the servers: new load', info['source'] == 'osm' and len(loads) == 4 and info['osmDate'] == version['osmDate'])
restart()
_, info = ms.matrix(coords, options, 'distances')
check('new data state: then from the cache', info['source'] == 'cache' and len(loads) == 4)

restart()
_, info0 = ms.matrix(coords, options, 'distances')                     # data state is known in this process
ms._recent.clear()
version = None                                                         # servers do not answer the status request
ms._versions['car'] = (time.time() - 1, ms._versions['car'][1])        # next check is due
_, info = ms.matrix(coords, options, 'distances')
check('status not available: last known data state', info['source'] == 'cache' and len(loads) == 4)

restart()
_, info = ms.matrix(coords, options, 'distances')
check('status never available: an own entry', info['source'] == 'osm' and 'osmDate' not in info and len(loads) == 5)

version = {'graphDate': '2025-04-01T03:00:00Z', 'osmDate': '2025-03-28T00:00:00Z'}
restart()
ms._versions.clear()
calls = []
ms._loadVersion = lambda travelmode: calls.append(travelmode) or version
for _ in range(5):
    ms._recent.clear()
    ms.matrix(coords, options, 'distances')
check('data state checked once per hour', len(calls) == 1)
ms._loadVersion = lambda travelmode: version


#*************** max age ************************************************
print('== max age')
fresh(maxAgeDays=0)
ms.matrix(coords, options, 'distances')
restart()
_, info = ms.matrix(coords, options, 'distances')
check('expired entries are loaded again', info['source'] == 'osm' and len(loads) == 2)
fresh()
check('default max age 180 days', ms._cache.maxAge == 180 * 86400)


#*************** bee line and errors ************************************************
print('== bee line, errors')
fresh()
b, info = ms.matrix(coords, MatrixItem(coordinates=coords, matrixSource='beeline', detourFactor=1.3), 'distances')
check('bee line without OSM servers', info['source'] == 'beeline' and len(loads) == 0 and b[0][1] > 0)
try:
    ms.matrix(coords, MatrixItem(coordinates=coords), 'costs')
    check('costs without cost rates', False)
except LogLabCoreException as e:
    check('costs without cost rates', e.httpStatus == 400, f'- {e}')


#*************** real servers ************************************************
print('== data state of the configured ORS servers')
try:
    import osm_data as osm
    osm.Config(optFile=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logisticsLabServer', 'logisticsLab.yml'))
    real = realLoadVersion('car')
    if real:
        check('graph_build_date of the servers', bool(real['graphDate']), real)
    else:
        print('skip   ORS servers not available')
except Exception as e:
    print(f'skip   OSM configuration not available - {e}')


print(f'== {nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

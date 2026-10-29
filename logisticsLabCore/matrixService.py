""" distance, time and cost matrices from coordinates - via the OSM servers or as bee line, with a cache

    The raw data of the OSM servers (distances in m, durations in s) are cached in a SQLite file. The factors
    (timeFactor, costPerKm, costPerHour) are applied afterwards, so a cache entry is valid for all factors.
    The key of an entry contains the data state of the ORS servers (graph_build_date of /ors/v2/status) - after an
    update of the servers the old entries are not used anymore. matrixCacheMaxAge is only a safety net.

        matrix(coordinates, options, kind)   kind: distances (m), times (s) or costs - returns (matrix, info)

    options is an item with the fields of MatrixOptions (items.py) - missing fields get their defaults.
    The cache is configured once per process with configure(conf), the solver processes have their own connection.
"""

from .exception import *

import osm_data as osm
from osm_data.tools import readConf

import collections
import copy
import hashlib
import json
import math
import os
import requests
import sqlite3
import threading
import time
import zlib


DEFAULT_SPEEDS = {'car': 50, 'foot': 5, 'wheelchair': 4}       # km/h - durations of bee line matrices
EARTH_RADIUS = 6371008.8                                        # m

ORS_PROFILES = {'car': 'driving-car', 'foot': 'foot-walking', 'wheelchair': 'wheelchair'}
VERSION_CHECK_INTERVAL = 3600                                   # s - the data state of the ORS servers is checked hourly

DEFAULTS = {'travelmode': 'car', 'matrixSource': 'osm', 'detourFactor': 1.0, 'averageSpeed': None, 'timeFactor': 1.0,
            'noCache': False, 'costPerKm': None, 'costPerHour': None}


#*************** cache ************************************************
class MatrixCache:
    """ raw OSM matrices in a SQLite file - shared by all processes of a server or an app

        An entry expires maxAgeDays after it has been loaded from the OSM servers (the OSM data change).
        If there are more than maxEntries entries, the least recently used ones are deleted.
        Errors of the cache never stop a request - the matrix is then loaded from the OSM servers.
    """

    def __init__(self, fileName, maxAgeDays=180, maxEntries=500, logger=None):
        self.fileName = fileName
        self.maxAge = maxAgeDays * 86400
        self.maxEntries = maxEntries
        self.__logger = logger
        os.makedirs(os.path.dirname(os.path.abspath(fileName)), exist_ok=True)
        with self.__connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS matrices (key TEXT PRIMARY KEY, created REAL, lastUsed REAL, data BLOB)')

    def __connect(self):
        db = sqlite3.connect(self.fileName, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')       # readers and one writer at the same time
        return db

    def __warn(self, message):
        if self.__logger:
            self.__logger.warning('matrixCache', message)

    def get(self, key):
        try:
            with self.__connect() as db:
                row = db.execute('SELECT created, data FROM matrices WHERE key=?', (key,)).fetchone()
                if row is None:
                    return None
                if time.time() - row[0] > self.maxAge:
                    db.execute('DELETE FROM matrices WHERE key=?', (key,))
                    return None
                db.execute('UPDATE matrices SET lastUsed=? WHERE key=?', (time.time(), key))
                return json.loads(zlib.decompress(row[1]))
        except Exception as e:
            self.__warn(f'read failed - {e}')
            return None

    def put(self, key, value):
        try:
            now = time.time()
            data = zlib.compress(json.dumps(value, separators=(',', ':')).encode('utf-8'))
            with self.__connect() as db:
                db.execute('INSERT OR REPLACE INTO matrices VALUES (?, ?, ?, ?)', (key, now, now, data))
                db.execute('DELETE FROM matrices WHERE created < ?', (now - self.maxAge,))
                db.execute('DELETE FROM matrices WHERE key NOT IN '
                           '(SELECT key FROM matrices ORDER BY lastUsed DESC LIMIT ?)', (self.maxEntries,))
        except Exception as e:
            self.__warn(f'write failed - {e}')

    def size(self):
        with self.__connect() as db:
            return db.execute('SELECT COUNT(*) FROM matrices').fetchone()[0]


_cache = None
_logger = None
# the last raw matrices of this process - e.g. distances and times of the same vrp, also without the cache
_recent = collections.OrderedDict()
_recentLock = threading.Lock()


def configure(conf, logger=None):
    """ conf: matrixCache (True/False), matrixCacheFile, matrixCacheMaxAge (days), matrixCacheMaxEntries """
    global _cache, _logger
    _logger = logger
    _cache = None
    if conf.get('matrixCache', True) and conf.get('matrixCacheFile'):
        try:
            _cache = MatrixCache(conf['matrixCacheFile'], conf.get('matrixCacheMaxAge', 180),
                                 conf.get('matrixCacheMaxEntries', 500), logger)
        except Exception as e:
            if logger:
                logger.warning('matrixCache', f'cache {conf["matrixCacheFile"]} not available - {e}')
#*************** end cache ************************************************


#*************** data state of the OSM servers ************************************************
_versions = {}                  # travelmode -> (time of the next check, data state or None)
_versionLock = threading.Lock()


def dataVersion(travelmode):
    """ data state {graphDate, osmDate} of the ORS matrix servers for the travel mode - None if unknown

        checked at most once per VERSION_CHECK_INTERVAL - if the servers do not answer, the last known state is used
    """
    now = time.time()
    with _versionLock:
        entry = _versions.get(travelmode)
        if entry and entry[0] > now:
            return entry[1]
    version = _loadVersion(travelmode)
    with _versionLock:
        if version is None and entry:
            version = entry[1]
        _versions[travelmode] = (now + VERSION_CHECK_INTERVAL, version)
    return version


def _loadVersion(travelmode):
    """ graph_build_date and osm_date of all configured ORS matrix servers - a matrix can come from each of them """
    profile = ORS_PROFILES.get(travelmode)
    try:
        conf = readConf()
    except Exception:
        return None
    graphDates, osmDates = set(), set()
    for server in conf.get('servers', {}).get('matrix', []):
        if server.get('type') != 'ors' or not profile:
            continue
        url = server['url'].rstrip('/').rsplit('/matrix', 1)[0] + '/status'
        headers = {'Authorization': server['api_key']} if server.get('api_key') else {}
        try:
            response = requests.get(url, headers=headers, timeout=(2, 5), proxies=conf.get('proxies') or None)
            data = response.json()['profiles'][profile]
        except Exception:
            continue
        if data.get('graph_build_date'):
            graphDates.add(data['graph_build_date'])
        if data.get('osm_date'):
            osmDates.add(data['osm_date'])
    if not graphDates:
        return None
    return {'graphDate': ','.join(sorted(graphDates)), 'osmDate': max(osmDates) if osmDates else None}
#*************** end data state ************************************************


def _opt(options, name):
    value = getattr(options, name, None)
    return DEFAULTS[name] if value is None else value


def cacheKey(coordinates, travelmode, sources, destinations, graphDate=None):
    """ coordinates rounded to 6 decimal places (about 0.1 m), graphDate: data state of the OSM servers """
    data = {'coordinates': [ [round(c[0], 6), round(c[1], 6)] for c in coordinates ], 'travelmode': travelmode,
            'sources': sources, 'destinations': destinations, 'graphDate': graphDate}
    return hashlib.sha256(json.dumps(data, separators=(',', ':')).encode('utf-8')).hexdigest()


def _beeLine(coordinates, options, sources, destinations):
    """ great-circle distance x detourFactor, durations with averageSpeed """
    detourFactor = _opt(options, 'detourFactor')
    speed = _opt(options, 'averageSpeed') or DEFAULT_SPEEDS.get(_opt(options, 'travelmode'), 50)
    rad = [ (math.radians(c[0]), math.radians(c[1])) for c in coordinates ]

    def dist(i, j):
        (la1, lo1), (la2, lo2) = rad[i], rad[j]
        h = math.sin((la2-la1)/2)**2 + math.cos(la1) * math.cos(la2) * math.sin((lo2-lo1)/2)**2
        return 2 * EARTH_RADIUS * math.asin(math.sqrt(h)) * detourFactor

    distances = [ [ dist(i, j) for j in destinations ] for i in sources ]
    durations = [ [ d / (speed / 3.6) for d in row ] for row in distances ]
    return {'distances': distances, 'durations': durations, 'source': 'beeline', 'status': 'beeline',
            'fillFactors': None, 'detourFactor': detourFactor, 'averageSpeed': speed}


def baseMatrix(coordinates, options, sources=None, destinations=None):
    """ raw matrices {distances (m), durations (s), source, status, fillFactors} - source: osm, cache or beeline """
    n = len(coordinates)
    sources = list(range(n)) if sources is None else list(sources)
    destinations = list(range(n)) if destinations is None else list(destinations)
    if _opt(options, 'matrixSource') == 'beeline':
        return _beeLine(coordinates, options, sources, destinations)

    travelmode = _opt(options, 'travelmode')
    version = dataVersion(travelmode)
    key = cacheKey(coordinates, travelmode, sources, destinations, version['graphDate'] if version else None)
    noCache = _opt(options, 'noCache')

    with _recentLock:
        if not noCache and key in _recent:
            _recent.move_to_end(key)
            return {**_recent[key], 'source': 'cache'}

    base = _cache.get(key) if (_cache and not noCache) else None
    if base is not None:
        base['source'] = 'cache'
    else:
        try:
            m = osm.Matrix(coordinates, sources=sources, destinations=destinations)
            status, msg = m.loadMatrix(travelmode=travelmode)
        except osm.OsmException as e:
            raise LogLabCoreException(str(e), e.status_code)
        if status != 200:
            raise LogLabCoreException(msg, status)
        base = {'distances': m.distanceMatrix, 'durations': m.timeMatrix, 'status': m.matrixStatus,
                'fillFactors': m.fillFactors, 'osmDate': version['osmDate'] if version else None}
        if _cache:
            _cache.put(key, base)
        base = {**base, 'source': 'osm'}
        if _logger:
            _logger.debug('matrix', f'{len(sources)}x{len(destinations)} {travelmode} loaded from the OSM servers')

    with _recentLock:
        _recent[key] = base
        while len(_recent) > 4:
            _recent.popitem(last=False)
    return base


def matrix(coordinates, options, kind, sources=None, destinations=None, rounded=True):
    """ matrix [sources x destinations] of the kind distances (m), times (s) or costs, and its info

        times:  durations x timeFactor
        costs:  km x costPerKm + h x timeFactor x costPerHour
        rounded: distances and times to integers, costs to 2 decimal places
    """
    if kind not in ('distances', 'times', 'costs'):
        raise LogLabCoreException(f'wrong matrix kind {kind}', 400)
    costPerKm, costPerHour = _opt(options, 'costPerKm'), _opt(options, 'costPerHour')
    if kind == 'costs' and costPerKm is None and costPerHour is None:
        raise LogLabCoreException('matrixMode costs needs costPerKm and/or costPerHour', 400)
    timeFactor = _opt(options, 'timeFactor')

    base = baseMatrix(coordinates, options, sources, destinations)
    if kind == 'distances':
        m = base['distances']
    elif kind == 'times':
        m = [ [ t * timeFactor for t in row ] for row in base['durations'] ]
    else:
        m = [ [ d / 1000 * (costPerKm or 0) + t * timeFactor / 3600 * (costPerHour or 0)
                for d, t in zip(dRow, tRow) ] for dRow, tRow in zip(base['distances'], base['durations']) ]

    if rounded:
        m = [ [ round(v, 2) for v in row ] for row in m ] if kind == 'costs' else [ [ round(v) for v in row ] for row in m ]
    else:
        m = copy.deepcopy(m)        # the raw matrices of the cache must not be changed

    info = {'source': base['source'], 'status': base['status'], 'travelmode': _opt(options, 'travelmode'),
            'matrices': [kind]}
    if base.get('fillFactors'):
        info['fillFactors'] = base['fillFactors']
    if base.get('osmDate'):
        info['osmDate'] = base['osmDate']           # data state of the OSM servers
    if base['source'] == 'beeline':
        info['detourFactor'] = base['detourFactor']
        if kind != 'distances':
            info['averageSpeed'] = base['averageSpeed']
    if kind != 'distances' and timeFactor != 1:
        info['timeFactor'] = timeFactor
    if kind == 'costs':
        info['costPerKm'] = costPerKm or 0
        info['costPerHour'] = costPerHour or 0
    return m, info


def mergeInfo(info, other):
    """ info of several matrices of the same problem (e.g. distances and times of a vrp) """
    if info is None:
        return other
    merged = {**info, **other}
    merged['source'] = info['source']           # e.g. osm - the second matrix uses the same raw data
    merged['matrices'] = info['matrices'] + [ k for k in other['matrices'] if k not in info['matrices'] ]
    return merged

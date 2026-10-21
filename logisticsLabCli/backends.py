""" backends of the command line tool - matrix(payload) and solve(payload) of scenario.py

    LocalBackend    the core of LogisticsLab in this process (OSM servers of confs/logisticsLab.yml)
    RemoteBackend   a LogisticsLab server (REST, api key)
"""

from logisticsLabCore import paths
from logisticsLabCore.scenario import ScenarioException

import json
import os
import time
import urllib.error
import urllib.request


#*************** backends ************************************************

class LocalBackend:
    """ the core in this process - the problems are solved in its solver processes """

    def __init__(self, logPath, osmConfig=None):
        from logisticsLabCore.core import LogisticsLabCore
        from logisticsLabCore.logger import CoreLogger
        os.makedirs(logPath, exist_ok=True)
        conf = {'maxProblems': 1, 'workDir': logPath, 'tpp': {'solverLogFile': os.path.join(logPath, 'HiGHS.log')}}
        osmConfig = osmConfig or paths.osmConfigFile()
        self.core = LogisticsLabCore(conf, CoreLogger(os.path.join(logPath, 'logisticsLabCli.log')),
                                     osmConfigFile=osmConfig, osmLogFile=os.path.join(logPath, 'logisticsLab.log'))

    def matrix(self, payload):
        from logisticsLabCore.exception import LogLabCoreException
        try:
            return self.core.geo('matrix', payload)
        except LogLabCoreException as e:
            raise ScenarioException(f'matrix: {e}')

    def solve(self, payload):
        from logisticsLabCore.exception import LogLabCoreException
        try:
            id = self.core.submit(payload)
        except LogLabCoreException as e:
            raise ScenarioException(str(e))
        except Exception as e:                       # validation errors of the items
            raise ScenarioException(f'wrong problem: {e}')
        while self.core.jobs.get(id).status in ('waiting', 'running'):
            time.sleep(0.1)
        content, _, _ = self.core.fetch(id)
        return content

    def close(self):
        self.core.shutdown()


class RemoteBackend:
    """ a LogisticsLab server (REST) - the results are polled via /v1/results """

    def __init__(self, url, apiKey):
        self.url = url if url.endswith('/') else url + '/'
        self.apiKey = apiKey

    def __post(self, endpoint, body):
        request = urllib.request.Request(self.url + endpoint, data=json.dumps(body).encode('utf-8'), method='POST',
                                         headers={'Content-Type': 'application/json', 'X-API-Key': self.apiKey})
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')
        except urllib.error.URLError as e:
            raise ScenarioException(f'server {self.url} not available: {e.reason}')

    def matrix(self, payload):
        code, answer = self.__post('matrix', payload)
        if code != 200:
            raise ScenarioException(f'matrix: {code} {answer.get("message") or answer.get("detail")}')
        return answer

    def solve(self, payload):
        code, answer = self.__post('solve', payload)
        if code != 200:
            raise ScenarioException(f'{code} {answer.get("message") or answer.get("detail") or answer}')
        while True:
            _, result = self.__post('results', {'id': answer['id']})
            if result.get('status') not in ('waiting', 'running'):
                return result
            time.sleep(0.3)

    def close(self):
        pass

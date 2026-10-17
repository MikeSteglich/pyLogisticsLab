""" small client for the server tests

    The settings are read from the environment or from .env in this directory (python createTestKeys.py):
        LOGLAB_API_KEY=...                      api key of the server
        LOGLAB_URL=http://127.0.0.1:8000/v1/    default: local server
    Variables of the environment have priority over .env.
"""

import requests
import os
import time


def loadEnv(fileName=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
    """ KEY=VALUE lines of .env into os.environ, without overwriting existing variables """
    if not os.path.isfile(fileName):
        return
    with open(fileName, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                name, value = line.split('=', 1)
                os.environ.setdefault(name.strip(), value.strip())

loadEnv()

url = os.environ.get('LOGLAB_URL', 'http://127.0.0.1:8000/v1/')

headers = {
    'X-API-Key': os.environ.get('LOGLAB_API_KEY', ''),
    'Content-Type': 'application/json'
}


def solve(endpoint, payload, verbose=True, timeout=600):
    """ submits a problem and polls its results - returns the last answer of /results """
    return solveWithStatus(endpoint, payload, verbose, timeout)[1]


def solveWithStatus(endpoint, payload, verbose=True, timeout=600, apiKey=None):
    """ as solve - returns (http status, answer) of the request or, if it has been accepted, of /results """
    h = {**headers, 'X-API-Key': apiKey} if apiKey else headers
    response = requests.post(url+endpoint, json=payload, headers=h)
    ret = response.json()
    if verbose:
        print(ret)
    if response.status_code != 200:
        return response.status_code, ret

    sTime = time.time()
    while True:
        response = requests.post(url+'results', json={"id": ret['id']}, headers=h)
        res = response.json()
        if res['status'] not in ['waiting', 'running']:
            break
        if time.time()-sTime > timeout:
            requests.post(url+'cancel', json={"id": ret['id']}, headers=h)
            raise TimeoutError(f'no result after {timeout} seconds')
        time.sleep(0.2)

    if verbose:
        print(res)
    return response.status_code, res


def _format(value):
    if isinstance(value, float):
        return f'{value:.4f}'.rstrip('0').rstrip('.')
    if isinstance(value, list):
        return '[' + ', '.join(_format(v) for v in value) + ']'
    return str(value)


def showResults(ret, title=None):
    """ prints the answer of /results - a matrix (e.g. flows, locations) row by row """
    if title:
        print(f'== {title}')
    results = ret.get('results', {})
    width = max([len(name) for name in results] + [len('status')]) + 2
    print(f"{'status':{width}}{ret.get('status')} - {ret.get('message', ret)}")
    for name, value in results.items():
        if isinstance(value, list) and value and all(isinstance(v, list) for v in value):
            print(f'{name}:')
            for i, row in enumerate(value):
                print(f'    {i:3}  {_format(row)}')
        else:
            print(f'{name:{width}}{_format(value)}')
    print()

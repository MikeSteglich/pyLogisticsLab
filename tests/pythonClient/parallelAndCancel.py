""" several problems at the same time, status notifications, a cancelled problem and a geo request

    python parallelAndCancel.py

    The local interface solves maxProblems (default 2) problems at the same time, further ones wait in the queue.
    The app is informed about every change of the status by jobStatus - no polling.
"""

from logisticsLabClient import LocalBackend, LogisticsLabException

import time


distances = [[0, 4, 7, 5, 6], [4, 0, 3, 6, 8], [7, 3, 0, 4, 7], [5, 6, 4, 0, 3], [6, 8, 7, 3, 0]]


def showStatus(name):
    sTime = time.time()
    return lambda s: print(f'{time.time() - sTime:5.1f}s  {name:8} {s["status"]:10} {s["message"]}')


with LocalBackend() as backend:
    # a vrp searches for maxSolvingTime seconds - it is cancelled below
    long = backend.submit({"type": "vrp", "distances": distances, "demands": [0, 4, 5, 3, 6], "capacities": [10, 10],
                           "maxSolvingTime": 30}, onStatus=showStatus('vrp'))
    tsp = backend.submit({"type": "tsp", "distances": distances}, onStatus=showStatus('tsp'))
    tpp = backend.submit({"type": "tpp", "varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
                          "supplies": [5000, 6000, 2500], "demands": [6000, 4000, 2000, 1500]}, onStatus=showStatus('tpp'))

    for name, id in (('tsp', tsp), ('tpp', tpp)):
        backend.wait(id, timeout=60)
        answer = backend.result(id)
        print(f"         {name:8} objVal {answer['results']['objVal']}")

    time.sleep(1)
    print('         cancel vrp')
    backend.cancel(long)
    backend.wait(long, timeout=30)
    print('         vrp     ', backend.result(long)['status'])

    # geo services answer directly - here a bee line matrix, it needs no OSM servers
    matrix = backend.geo('matrix', {"coordinates": [[52.52, 13.40], [52.39, 13.06], [52.41, 12.55]],
                                    "matrixSource": "beeline", "matrixMode": "costs", "costPerKm": 0.5})
    print('         bee line cost matrix', matrix['costs'], matrix['matrixInfo']['source'])

    # wrong fields are rejected immediately with the http status of the REST server
    try:
        backend.submit({"type": "tsp", "distance": distances})
    except LogisticsLabException as e:
        print('        ', e)

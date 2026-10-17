""" vehicle routing problem via the LogisticsLab server (/v1/vrp)

    Start the local server and register the example key once:
        python tests/serverTests/createTestKeys.py
        cd logisticsLabServer && ./run_server.sh
    The example key is public - it is only valid on the local server.
"""

import requests
import time


url = 'http://127.0.0.1:8000/v1/'
apiKey = 'loglab-local-example-key'        # the key itself is sent, the server knows only its hash

headers = {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
}

# depot 0, 4 customers, 2 vehicles with capacity 10
payload = {
    "distances": [[0, 4, 7, 5, 6], [4, 0, 3, 6, 8], [7, 3, 0, 4, 7], [5, 6, 4, 0, 3], [6, 8, 7, 3, 0]],
    "demands": [0, 4, 5, 3, 6],
    "capacities": [10, 10],
    "depot": 0,
    "maxSolvingTime": 2
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'vrp', json=payload, headers=headers)
answer = response.json()
if response.status_code != 200:
    print('problem rejected:', response.status_code, answer)
    raise SystemExit(1)
problemId = answer['id']
print('problem submitted:', problemId)

# poll the results until the problem is finished
while True:
    response = requests.post(url + 'results', json={'id': problemId}, headers=headers)
    answer = response.json()
    if answer['status'] not in ('waiting', 'running'):
        break
    time.sleep(0.5)

print('status:', answer['status'], '-', answer['message'])
if answer['status'] == 'solution':
    results = answer['results']
    print('objVal            ', results['objVal'])
    print('routes:')
    for i, row in enumerate(results['routes']):
        print('   ', i, row)
    print('routeLoads:')
    for i, row in enumerate(results['routeLoads']):
        print('   ', i, row)
    print('routeDistances:')
    for i, row in enumerate(results['routeDistances']):
        print('   ', i, row)

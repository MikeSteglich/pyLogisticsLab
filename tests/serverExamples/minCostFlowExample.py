""" min cost flow problem via the LogisticsLab server (/v1/mincostflow)

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

# node 0 supplies 20 units, nodes 2 and 3 demand 5 and 15
payload = {
    "edges": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
    "costs": [4, 4, 2, 2, 1],
    "supplies": [20, 0, 0, 0],
    "demands": [0, 0, 5, 15],
    "maxCaps": [15, 8, 20, 5, 10]           # null or "M": unlimited
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'mincostflow', json=payload, headers=headers)
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
    print('flows             ', results['flows'])

""" maximal covering problem via the LogisticsLab server (/v1/mcp)

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

# open 1 source (fixed costs 1) - maximal demand within radius 3
payload = {
    "distances": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
    "radius": 3,
    "demands": [6, 4, 2, 1],
    "maxSrcCost": 1
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'mcp', json=payload, headers=headers)
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
    print('activeSources     ', results['activeSources'])
    print('coveringSources   ', results['coveringSources'])
    print('assignments       ', results['assignments'])

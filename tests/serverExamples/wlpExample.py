""" warehouse location problem via the LogisticsLab server (/v1/wlp)

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

# 3 possible warehouses with fixed costs and capacities, 4 customers
payload = {
    "varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
    "fixedCosts": [5000, 4000, 6000],
    "demands": [600, 400, 200, 150],
    "supplies": [800, 700, 600],
    "isCapacitated": True
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'wlp', json=payload, headers=headers)
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
    print('assignments       ', results['assignments'])

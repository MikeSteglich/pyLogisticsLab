""" travelling salesman problem with coordinates via the LogisticsLab server (/v1/tsp)

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

# coordinates [lat, lon] - the server loads the road distances from the OSM servers
payload = {
    "coordinates": [[52.516275, 13.377704], [52.521918, 13.413215], [52.510972, 13.434567], [52.39, 13.06]],
    "travelmode": "car"
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'tsp', json=payload, headers=headers)
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
    print('route             ', results['route'])

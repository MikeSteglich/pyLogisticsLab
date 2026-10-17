""" continuous p-median problem via the LogisticsLab server (/v1/contpmedian)

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

# 3 facilities anywhere in Brandenburg - customers [lat, lon] and their demands, great-circle distances in km
payload = {
    "p": 3,
    "coordinates": [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
                    [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]],
    "demands": [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8],
    "capacities": 100,              # null: uncapacitated
    "isSingleSource": True          # False: the demand of a customer can be split
}

# submit the problem - the server answers with the id of the problem
response = requests.post(url + 'contpmedian', json=payload, headers=headers)
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
    print('locations:')
    for i, row in enumerate(results['locations']):
        print('   ', i, row)
    print('assignments       ', results['assignments'])
    print('customerDistances ', results['customerDistances'])

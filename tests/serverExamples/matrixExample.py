""" distance and time matrix via the LogisticsLab server (/v1/matrix)

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

# coordinates [lat, lon] - distances in m, durations in s
payload = {
    "coordinates": [[52.516275, 13.377704], [52.521918, 13.413215], [52.510972, 13.434567], [52.39, 13.06]],
    "travelmode": "car",            # the OSM servers of the TH Wildau only provide car
    "matrixMode": "both",           # distances, durations or both
    "rounded": True
}

# geo services answer directly - no id and no polling
response = requests.post(url + 'matrix', json=payload, headers=headers)
answer = response.json()
print('http', response.status_code, '-', answer.get('status'), '-', answer.get('message'))
if response.status_code == 200:
    print('distances:')
    for i, row in enumerate(answer['distances']):
        print('   ', i, row)
    print('durations:')
    for i, row in enumerate(answer['durations']):
        print('   ', i, row)

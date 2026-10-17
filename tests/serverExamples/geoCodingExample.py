""" coordinates of addresses via the LogisticsLab server (/v1/coordinates)

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

# coordinates [lat, lon] of addresses - see also /v1/search (one address, several hits) and /v1/reverse
payload = {
    "adresses": ['Schönwalde,16348,DE', 'Klosterfelde', 'Marchlewskistr. 43, 10243 Berlin']
}

# geo services answer directly - no id and no polling
response = requests.post(url + 'coordinates', json=payload, headers=headers)
answer = response.json()
print('http', response.status_code, '-', answer.get('status'), '-', answer.get('message'))
if response.status_code == 200:
    print('coordinates:')
    for i, row in enumerate(answer['coordinates']):
        print('   ', i, row)

import requests
import os

import time


time_start = time.time()

adress = 'Schönwalde,16348,DE'


url = 'http://127.0.0.1:8000/v1/'


payload = {
    "adress": adress
}

headers = {
    'X-API-Key': os.environ.get('LOGLAB_API_KEY', ''),   # export LOGLAB_API_KEY=...
    'Content-Type': 'application/json'
}


response = requests.post(url+'search', json=payload, headers=headers)
ret = response.json()
print(ret)



print("... done {}".format(time.time() - time_start))

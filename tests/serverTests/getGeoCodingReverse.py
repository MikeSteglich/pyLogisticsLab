import requests
import os

import time


time_start = time.time()

coords = (  52.7965937,  13.4801974)


url = 'http://127.0.0.1:8000/v1/'


payload = {
    "coordinate": coords
}

headers = {
    'X-API-Key': os.environ.get('LOGLAB_API_KEY', ''),   # export LOGLAB_API_KEY=...
    'Content-Type': 'application/json'
}


response = requests.post(url+'reverse', json=payload, headers=headers)
ret = response.json()
print(ret)



print("... done {}".format(time.time() - time_start))

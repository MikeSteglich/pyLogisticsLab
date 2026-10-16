import requests

import time


time_start = time.time()
coords = [
    #[13.782719, 52.824551], # Punkt 1 (Zoo-Bereich)
    [  13.782705, 52.824499],
    #[13.779999, 52.822915]  # Punkt 2 (Zoo-Bereich)
    #[13.780063, 13.780063]
    #[13.780189, 52.822843]
   
    [  13.782424,52.822410]
    #[ 13.782349, 52.822315]
    #[ 13.779999, 52.822915]
]

tMode = 'wheelchair' #'foot-walking'


#url = 'http://127.0.0.1:8000/v1/'
#url = f'http://88.218.227.150:5000/ors/v2/directions/{tMode}/geojson'
url = f'http://zoo-ew-api.de:5000/ors/v2/directions/{tMode}/geojson'


payload={'coordinates': coords, 'geometry_simplify': 'false', 'instructions': 'false', 'radiuses': [-1]}

headers = {'Referer': 'http://logisticsLab.org', 'User-Agent': 'LogisticsLab', 'Content-Type': 'application/json', 'charset': 'utf-8', 'Accept-Language': 'en-GB, en-US'}


response = requests.post(url, json=payload, headers=headers)
ret = response.json()
print(ret)



print("... done {}".format(time.time() - time_start))

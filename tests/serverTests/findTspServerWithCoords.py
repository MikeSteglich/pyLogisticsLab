import requests
import time


coords = [ [44.43,26.1],
[52.52,13.4],
[50.85,4.35],
[47.5,19.04],
[44.82,20.47],
[52.37,4.9],
[55.68,12.57],
[46.95,7.44],
[37.98,23.73],
[48.15,17.11]
]

url = 'http://127.0.0.1:8000/v1/'


payload = {
    "coordinates": coords
}

headers = {
#    'Authorization': api_key,
    'Content-Type': 'application/json'
}


response = requests.post(url+'tsp', json=payload, headers=headers)
ret = response.json()
print(ret)

id = ret['id']

payload = {
    "id": id
}


while True:
    response = requests.post(url+'results', json=payload, headers=headers)
    ret = response.json()
    print(ret)
    time.sleep(0.2)
    if ret['status'] in ['solution', 'noSolution', 'error']:
        break

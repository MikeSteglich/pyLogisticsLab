import requests
import time


varCosts = [[3, 2, 7, 6],
            [7, 5, 2, 3],
            [2, 5, 4, 5]]

supplies = [5000, 6000, 2500]
demands = [6000, 4000, 2000, 1500]

url = 'http://127.0.0.1:8000/v1/'
#url = 'http://152.89.239.234:8000/v1/'


payload = {
    "varCosts": varCosts,
    "supplies": supplies,
    "demands": demands,
    "objSense": "min"
}

headers = {
    'Content-Type': 'application/json'
}


response = requests.post(url+'tpp', json=payload, headers=headers)
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

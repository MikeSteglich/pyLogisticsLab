import requests

# REIHENFOLGE GEÄNDERT: [Longitude, Latitude]
'''coords = [
    #[13.782719, 52.824551], # Punkt 1 (Zoo-Bereich)
    [13.782705, 52.824499],
    #[13.779999, 52.822915]  # Punkt 2 (Zoo-Bereich)
    #[13.780063, 13.780063]
    #[13.780189, 52.822843]
   
    [ 13.780112, 52.822875]
    #[ 13.779999, 52.822915]
]'''

#coords = [[52.82329251885275, 13.780568321395375], [52.82353493645306, 13.780637651677809]]
coords = [[13.781145121837762, 52.82319981920678], [ 13.781353533267977, 52.823005099112216]]

url = 'http://88.218.227.150:5000/ors/v2/matrix/foot-walking'

body = {
    "locations": coords,
    "metrics": ["distance"]
}

body = {'locations': coords, 'destinations': [0, 1], 'sources': [0, 1]}



headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json; charset=utf-8'
}

response = requests.post(url, json=body, headers=headers)
if response.status_code == 200:
    print(response.json())
else:
    print(f"Fehler {response.status_code}:")
    print(response.json())
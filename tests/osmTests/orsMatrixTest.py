import requests

# REIHENFOLGE GEÄNDERT: [Longitude, Latitude]
coords = [
    #[13.782719, 52.824551], # Punkt 1 (Zoo-Bereich)
    (13.782705, 52.824499),
    #[13.779999, 52.822915]  # Punkt 2 (Zoo-Bereich)
    #[13.780063, 13.780063]
    #[13.780189, 52.822843]

    ( 13.782349, 52.822315)
   
    #( 13.780112, 52.822875)
    #[ 13.779999, 52.822915]
]


url = 'http://88.218.227.150:5000/ors/v2/matrix/wheelchair'

'''body = {
    "locations": coords,
    "metrics": ["distance"]
}'''

#body = {'locations': coords, 'destinations': [0, 1], 'sources': [0, 1]}

body={'locations': coords, 'destinations': [0, 1], 'sources': [0, 1], 'metrics': ['distance', 'duration'], 'units': 'm'}

headers = {
            'Referer' : 'http://logisticsLab.org',
            'User-Agent': 'LogisticsLab',
            'Content-Type': 'application/json',
            'charset' : 'utf-8',
            'Accept-Language': 'en-GB, en-US'
        }

'''headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json; charset=utf-8'
}'''

response=requests.post(url, json=body, headers=headers, timeout=(3,120))
       

#response = requests.post(url, json=body, headers=headers)


if response.status_code == 200:
    print(response.json())
else:
    print(f"Fehler {response.status_code}:")
    print(response.json())
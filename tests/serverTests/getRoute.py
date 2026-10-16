import requests

import time


time_start = time.time()
'''coords = ((47.07087,15.43828),
(49.45387,11.0773),
(51.01348,2.303),
(51.51828,-2.54374),
(44.34632,8.54443),
(42.54072,1.5732),
(51.6177,5.43625),
(43.11772,5.80088),
(52.144,10.77519),
(47.61309,20.75023),
(47.59148,-2.45712),
(51.4825,11.97055)
)'''
#coords =  [[52.517037,13.388860],[52.529407, 13.397634],[52.523219,13.428555] ]


coords = [[13.782697, 52.824443], [  13.784162, 52.821606 ] ] #[[  13.784280, 52.821632], [ 13.780734, 52.822741]] 
tMode = 'foot'
routeDetails = 'simplified' 


#url = 'http://127.0.0.1:8000/v1/'
url = 'http://88.218.227.150:5000/ors/v2/directions/foot-walking/geojson'


payload = {
    "coordinates": coords,
 #   "travelmode" : tMode,
 #   "details" : routeDetails
}

headers = {
#    'Authorization': api_key,
    'Content-Type': 'application/json'
}


response = requests.post(url, json=payload, headers=headers)
ret = response.json()
print(ret)



print("... done {}".format(time.time() - time_start))

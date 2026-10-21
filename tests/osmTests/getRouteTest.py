import osm_data as osm
import time


import sys
import traceback

time_start = time.time()

coords = [
    #[13.782719, 52.824551], # Punkt 1 (Zoo-Bereich)
    [52.824499,  13.782705],
    #[13.779999, 52.822915]  # Punkt 2 (Zoo-Bereich)
    #[13.780063, 13.780063]
    #[13.780189, 52.822843]
    #[52.822478, 13.782378]
    #[52.822316, 13.782343]
    #[52.822289, 13.782475]
    [52.822475, 13.782394]
    #[ 52.822875, 13.780112]
    #[ 13.779999, 52.822915]
]


tMode = 'wheelchair'
routeDetails = 'full'

try:
    osm.Config()                                     # confs/logisticsLab.yml

    osmData = osm.Routing(coords)
    status, msg= osmData.loadRoute(travelmode=tMode, details=routeDetails)

    if status!=200:
        print(msg)
    else:
        route = osmData.route
        print(route)
        print(len(route))

    del osmData

        

except osm.OsmException as e: 
    print(e)
    #traceback.print_exc()


print("... done {}".format(time.time() - time_start))

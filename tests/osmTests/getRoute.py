import osm_data as osm
import time


import sys
import traceback

time_start = time.time()

#coords =  [[52.517037,13.388860],[52.529407, 13.397634],[52.523219,13.428555] ]
#coords1 = [[52.791, 13.4803], [52.8518, 13.5276], [52.9042, 13.5328], [52.8728, 13.5651], [52.8726, 13.3944], [52.7785, 13.4392], [52.791, 13.4803]]
#coords = ((52.791, 13.4803), (52.7546, 13.473), (52.7161, 13.4372), (52.6818, 13.4378), (52.7291, 13.3868), (52.7555, 13.3756), (52.7678, 13.3245), (52.791, 13.4803))
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
coords = [[52.82319981920678, 13.781145121837762], [52.823005099112216, 13.781353533267977]]

tMode = 'foot'
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

import osm_data as osm
import time

import sys
import traceback

time_start = time.time()

#coords =  [[52.517037,13.388860],[52.529407, 13.397634],[52.523219,13.428555] ]
coords1 = [[52.791, 13.4803], [52.8518, 13.5276], [52.9042, 13.5328], [52.8728, 13.5651], [52.8726, 13.3944], [52.7785, 13.4392], [52.791, 13.4803]]
coords = ((52.791, 13.4803), (52.7546, 13.473), (52.7161, 13.4372), (52.6818, 13.4378), (52.7291, 13.3868), (52.7555, 13.3756), (52.7678, 13.3245), (52.791, 13.4803))
tMode = 'car'
routeDetails = 'full'

try:
    #conf = osm.Config(optFile='logisticsLab.yml')

    for i in range(20): 
        osmData = osm.Routing(coords1, optFile='logisticsLab.yml')
        status, msg= osmData.loadRoute(travelmode=tMode, details=routeDetails)

        if status!=200:
            print(msg)
        else:
            route = osmData.route
            #print(route)
            print(i,',',len(route))


except osm.OsmException as e: 
    print(e)
    traceback.print_exc()


print("... done {}".format(time.time() - time_start))

import osm_data as osm
import time

import traceback

time_start = time.time()

#coords =  ((52.517037,13.388860),(52.529407, 13.397634),(52.523219,13.428555) )
coords = [
    #[13.782719, 52.824551], # Punkt 1 (Zoo-Bereich)
    [52.824499,  13.782705],
    #[13.779999, 52.822915]  # Punkt 2 (Zoo-Bereich)
    #[13.780063, 13.780063]
    #[13.780189, 52.822843]
   
    [ 52.822875, 13.780112]
    #[ 13.779999, 52.822915]
]


try:
    conf = osm.Config(optFile='logisticsLab.yml')

    osmData = osm.Matrix(coords)
    status, msg= osmData.loadMatrix(travelmode='foot')

    if status!=200:
        print(msg)
    else:
        distances = osmData.distanceMatrix
        durations = osmData.timeMatrix

        print(distances)
        #print(durations)

        #print(distances[3][7])

except osm.OsmException as e: 
    print(e, e.status_code)
    #traceback.print_exc()


print("... done {}".format(time.time() - time_start))

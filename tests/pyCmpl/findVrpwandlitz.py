from pyLogisticsLab import Vrp as vrp
import sys
import traceback


time_matrix =[[0, 6, 15, 18, 21, 13, 20, 23, 35, 29, 36, 37],
               [6, 0, 8, 12, 14, 7, 14, 16, 29, 23, 29, 31], 
               [15, 8, 0, 10, 7, 9, 6, 15, 23, 15, 22, 23], 
               [18, 12, 10, 0, 9, 7, 15, 4, 17, 25, 30, 32], 
               [21, 14, 7, 9, 0, 13, 8, 11, 16, 17, 23, 25], 
               [13, 7, 9, 7, 13, 0, 14, 11, 24, 24, 30, 31],
                 [20, 14, 6, 16, 8, 15, 0, 19, 19, 9, 16, 17],
                   [23, 17, 15, 5, 11, 11, 19, 0, 19, 28, 33, 34], 
                   [35, 29, 23, 17, 16, 24, 19, 19, 0, 10, 14, 15],
                     [29, 23, 15, 25, 17, 24, 9, 28, 10, 0, 7, 8],
                     [36, 29, 22, 30, 23, 30, 16, 33, 14, 7, 0, 8], 
                     [37, 31, 23, 32, 25, 32, 17, 34, 15, 8, 8, 0]]

time_windows = [[60, 120], [30, 120], [0, 60], [0, 60], [0, 45], [0, 30], [0, 3600], [150, 180], [60, 180], [180, 240], [0, 120], [0, 60]]
service_time = [5, 5, 5, 5, 5, 5, 0, 5, 5, 5, 5, 5]

distance_matrix = [[0, 4, 10, 13, 14, 9, 14, 17, 27, 21, 28, 26],
                    [4, 0, 5, 9, 10, 4, 9, 12, 22, 17, 23, 22], [10, 5, 0, 8, 4, 8, 4, 12, 18, 12, 18, 17], [13, 8, 8, 0, 7, 6, 12, 4, 14, 20, 29, 28], [14, 10, 4, 7, 0, 8, 6, 9, 14, 13, 20, 18], [9, 4, 8, 6, 8, 0, 12, 9, 20, 19, 26, 24], [14, 9, 4, 12, 6, 12, 0, 14, 19, 8, 14, 13], [17, 12, 12, 4, 9, 9, 14, 0, 16, 22, 31, 30], [27, 22, 18, 14, 14, 20, 19, 16, 0, 11, 16, 14], [21, 17, 12, 20, 13, 19, 8, 22, 11, 0, 6, 5], [28, 23, 18, 29, 20, 26, 14, 31, 16, 6, 0, 5], [26, 22, 17, 28, 18, 25, 13, 30, 14, 5, 5, 0]]

demands = [45, 50, 30, 20, 10, 75, 0, 60, 80, 100, 90, 15]
vehicle_capacities = [300, 300, 300]
depot = 6

maxSolvingTime = 1

#maxTime = 420
#maxDist = 200
useTW = False

maxTime = 0
maxDist = 0
#useTW = False


try:
    
    m =vrp.Vrp(distance_matrix ,demands, vehicle_capacities , depot , time_matrix, time_windows, service_time )

    if maxTime > 0:
        m.setMaxTime(maxTime)
    if maxDist >0:
        m.setMaxDist(maxDist)
    m.useTimeWindows(useTW)
    m.setMaxSolvingTime(maxSolvingTime)
    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        routeIndices = m.getRouteIndices()
        routeLoads = m.getRouteLoads()
        routeTimes = m.getRouteTimes()
        routeDistances = m.getRouteDistances()
    else:
        objVal = -1

except vrp.VrpException as e: 
    vrpOK = False
    vrpMsg = e
    traceback.print_exc()
except:
    vrpOK = False
    vrpMsg = str(sys.exc_info())
    traceback.print_exc()
else:
    vrpOK = True
    vrpMsg = "OK" 

print (vrpMsg)
 
if objVal>=0:
    print('obj ',objVal)
    print('indices ',routeIndices)
    print('loads ',routeLoads)
    print('times ' ,routeTimes)
    print('dists', routeDistances)
else:
    print('no solution found')
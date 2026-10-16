import pyLogisticsLab as ll
import sys
import traceback

time_matrix = [[0,60,120,104,51,135,95,38,132,101,122,126],
[60,0,87,135,83,75,155,98,164,161,182,186],
[120,87,0,68,69,162,215,158,150,204,242,246],
[104,135,68,0,53,210,198,141,134,188,225,230],
[51,83,69,53,0,158,146,89,81,135,173,177],
[143,83,170,218,165,0,108,180,246,243,186,231],
[95,155,215,198,146,108,0,105,222,168,78,123],
[38,98,158,141,89,173,105,0,117,63,84,89],
[132,164,150,134,81,239,200,95,0,54,179,183],
[101,161,204,188,135,236,168,63,54,0,147,152],
[122,182,242,225,173,186,78,84,201,147,0,45],
[126,186,246,230,177,231,123,89,206,152,45,0]]

time_windows = [(0,420),(30,150),(120,240),(120,240),(30,150),(180,300),(120,240),(30,150),(120,240),(180,300),(180,300),(180,300)]
service_time = [0,25,25,25,25,25,25,25,25,25,25,10]

distance_matrix = [[0,40,80,69,34,90,63,25,88,67,81,84],
[40,0,58,90,55,50,103,65,109,107,121,124],
[80,58,0,45,46,108,143,105,100,136,161,164],
[69,90,45,0,35,140,132,94,89,125,150,153],
[34,55,46,35,0,105,97,59,54,90,115,118],
[95,55,113,145,110,0,72,120,164,162,124,154],
[63,103,143,132,97,72,0,70,148,112,52,82],
[25,65,105,94,59,115,70,0,78,42,56,59],
[88,109,100,89,54,159,133,63,0,36,119,122],
[67,107,136,125,90,157,112,42,36,0,98,101],
[81,121,161,150,115,124,52,56,134,98,0,30],
[84,124,164,153,118,154,82,59,137,101,30,0]]

demands = [0,2100,2550,1100,3020,1000,3020,2400,1250,1000,2500,750]
vehicle_capacities = [4500, 4500, 4500, 4500, 4500, 4500, 4500]
depot = 0

maxSolvingTime = 3

#maxTime = 420
#maxDist = 200
#useTW = True

maxTime = 0
maxDist = 0
useTW = True


try:
    m =ll.Vrp(distance_matrix ,demands, vehicle_capacities , depot , time_matrix, time_windows, service_time )

    if maxTime > 0:
        m.setMaxTime(maxTime)
    if maxDist >0:
        m.setMaxDist(maxDist)
    m.useTimeWindows(useTW)
    #m.setMaxSolvingTime(maxSolvingTime)

    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        routeIndices = m.getRouteIndices()
        routeLoads = m.getRouteLoads()
        routeTimes = m.getRouteTimes()
        routeDistances = m.getRouteDistances()
    else:
        objVal = -1

except ll.LogLabException as e: 
    print(e)
    traceback.print_exc()
except:
    print( str(sys.exc_info()))
    traceback.print_exc()
else:
 
    if objVal>=0:
        print('obj ',objVal)
        print('indices ',routeIndices)
        print('loads ',routeLoads)
        print('times ' ,routeTimes)
        print('dists', routeDistances)
    else:
        print('no solution found')
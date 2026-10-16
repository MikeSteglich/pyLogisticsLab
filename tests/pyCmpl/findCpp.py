import pyLogisticsLab as ll
import sys


edges = [[1, 2], [2, 3], [2, 6], [3, 4], [3, 7], [4, 5], [4, 8], [5, 3], [5, 7], [5, 8], [5, 10], [6, 3], [6, 4], [7, 10], [9, 10], [9, 11], [9, 12], [10, 12], [12, 11]]
weights = [416, 540, 437, 785, 412, 712, 396, 445, 559, 886, 1339, 759, 574, 782, 1093, 1558, 1444, 513, 509]
types = [1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1]

startNode=7

try:

    m =ll.Cpp(edges, types, weights, startNode )
    m.solve()
    if m.isEulerTour():
        eulerTour = m.getEulerTour()
        lenTour = len(eulerTour)
        edgeUsages = m.getEdgeUsages()
        print(eulerTour, edgeUsages )

except ll.LogLabException as e: 
    print(e)
except:
   print(str(sys.exc_info()))



import pyLogisticsLab as ll

import traceback


# customers in Brandenburg [lat, lon] and their demands
coordinates = [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
               [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]]
demands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8]


def show(name, m):
    m.solve()
    if m.isSolution():
        print(f'== {name}: {round(m.getObjValue(), 2)} km')
        print('locations  ', [[round(v, 4) for v in l] for l in m.getLocations()])
        print('assignments', m.getAssignments())
    else:
        print(f'== {name}: {m.getMessage()}')


try:
    show('p-median, uncapacitated', ll.ContPMedian(3, coordinates, demands))
    show('p-median, capacity 100, single-source', ll.ContPMedian(3, coordinates, demands, capacities=100))
    show('p-median, capacity 100, split demands', ll.ContPMedian(3, coordinates, demands, capacities=100, isSingleSource=False))
    show('p-centre, uncapacitated', ll.ContPCentre(3, coordinates))
    show('p-centre, capacities 100, 100, 60, single-source', ll.ContPCentre(3, coordinates, demands, capacities=[100, 100, 60]))

except ll.LogLabException as e:
    print(e)
except:
    traceback.print_exc()

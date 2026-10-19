""" regression test of the pyLogisticsLab models - the same problems as tests/serverTests/checkServer.py

    python checkLibrary.py      (project directory in PYTHONPATH)
"""

import pyLogisticsLab as ll

import math
import sys
import traceback


nrOfErrors = 0

def check(name, model, expected, isSolved=None, heuristic=False, maximize=False):
    """ solves the model and compares the objective value with the expected one
        heuristic: a better value is ok as well
    """
    global nrOfErrors
    try:
        model.solve()
        isSolved = model.isSolution() if isSolved is None else isSolved(model)
        if not isSolved:
            isOk, info = False, '- no solution'
        else:
            objVal = model.getObjValue()
            tol = 1e-3 * max(1, abs(expected))
            if heuristic:
                isOk = objVal >= expected - tol if maximize else objVal <= expected + tol
            else:
                isOk = abs(objVal - expected) <= tol
            info = f'- objVal {objVal}, expected {expected}'
    except Exception:
        isOk, info = False, '- ' + traceback.format_exc()
    if not isOk:
        nrOfErrors += 1
    print(f"{'ok    ' if isOk else 'FAILED'} {name} {info}")

def checkException(name, create):
    """ the model has to raise a LogLabException - while creating or solving it """
    global nrOfErrors
    try:
        create().solve()
        isOk, info = False, '- no exception'
    except ll.LogLabException as e:
        isOk, info = True, f'- {str(e).strip()[:90]}'
    if not isOk:
        nrOfErrors += 1
    print(f"{'ok    ' if isOk else 'FAILED'} {name} {info}")


costs = [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]]

edges = [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]]
supplies = [20, 0, 0, 0]
demands = [0, 0, 5, 15]
maxCaps = [15, 8, 20, 5, 10]

coordinates = [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
               [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]]
contDemands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8]


print('== location and covering')
check('wlp', ll.Wlp(costs, [5000, 4000, 6000], [800, 700, 600], [600, 400, 200, 150], True), 14100)
check('pmedian', ll.PMedian(2, costs, [0, 0, 0], [6, 4, 2, 1], False, True), 33)
check('pcentre', ll.PCentre(2, costs, [0, 0, 0], [1, 1, 1, 1], False, False), 3)
check('scp', ll.Scp(costs, 3), 2)
check('mcp', ll.Mcp(costs, 3, 1, [6, 4, 2, 1]), 10)

print('== routing')
check('cpp', ll.Cpp([[1, 2], [2, 3], [3, 4], [4, 1], [1, 3]], [1] * 5, [4, 3, 5, 2, 6], 1), 26,
      isSolved=lambda m: m.isEulerTour())
vrp = ll.Vrp([[0, 4, 7, 5, 6], [4, 0, 3, 6, 8], [7, 3, 0, 4, 7], [5, 6, 4, 0, 3], [6, 8, 7, 3, 0]],
             [0, 4, 5, 3, 6], [10, 10], 0, [], [], [])
vrp.useTimeWindows(False)
vrp.setMaxSolvingTime(2)
check('vrp', vrp, 28, heuristic=True)

print('== network flows')
check('mincostflow', ll.MinCostFlow(edges, [4, 4, 2, 2, 1], supplies, demands, maxCaps=maxCaps), 114)
check('mincostflow fixed costs 0 = LP', ll.MinCostFlow(edges, [4, 4, 2, 2, 1], supplies, demands, maxCaps=maxCaps,
                                                       fixedCosts=[0] * 5), 114)
fixed = dict(costs=[4, 3, 2, 2, 1], maxCaps=[15, 15, 20, 10, 15], fixedCosts=[10, 60, 10, 30, 10])
check('mincostflow fixed costs', ll.MinCostFlow(edges, fixed['costs'], supplies, demands, maxCaps=fixed['maxCaps'],
                                                fixedCosts=fixed['fixedCosts']), 180)
# fixed charge flow = multimodal flow with one mode
check('multimodal one mode = mincostflow fixed costs',
      ll.MultiModalFlow(edges, [[c] for c in fixed['costs']], supplies, demands, fixedCosts=[[f] for f in fixed['fixedCosts']],
                        maxCaps=[[c] for c in fixed['maxCaps']]), 180)
check('maxflow', ll.MaxFlow(edges, 0, 3, maxCaps), 15)
check('multicommodity', ll.MultiCommodityFlow(edges, [[4, 1], [4, 1], [2, 1], [2, 1], [1, 1]],
                                              [[10, 5], [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [10, 5]],
                                              maxCaps=[15, 8, 20, 'M', 10]), 62)
check('multimodal', ll.MultiModalFlow(edges, [[4, 1], [4, None], [2, None], [2, 1], [1, None]], supplies, demands,
                                      fixedCosts=[[0, 30], [0, 0], [0, 0], [0, 30], [0, 0]],
                                      minCaps=[[0, 10], [0, 0], [0, 0], [0, 10], [0, 0]]), 90)
# with one commodity / mode and without fixed costs all flow models give the min cost flow
check('multicommodity = mincostflow', ll.MultiCommodityFlow(edges, [[c] for c in [4, 4, 2, 2, 1]],
                                                            [[s] for s in supplies], [[d] for d in demands],
                                                            maxCaps=maxCaps), 114)
check('multimodal = mincostflow', ll.MultiModalFlow(edges, [[c] for c in [4, 4, 2, 2, 1]], supplies, demands,
                                                    maxCaps=[[c] for c in maxCaps]), 114)

print('== continuous location')
check('contpmedian', ll.ContPMedian(3, coordinates, contDemands), 4968.608, heuristic=True)
check('contpmedian capacitated, split', ll.ContPMedian(3, coordinates, contDemands, capacities=100, isSingleSource=False),
      6039.286, heuristic=True)
check('contpcentre', ll.ContPCentre(3, coordinates), 42.566, heuristic=True)
check('contpcentre capacitated, single-source', ll.ContPCentre(3, coordinates, contDemands, capacities=[100, 100, 60]),
      56.541, heuristic=True)
# the continuous solution is never worse than the discrete one with the customers as candidates (haversine distances)
def haversine(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1) * math.cos(la2) * math.sin((lo2-lo1)/2)**2
    return 2 * ll.EARTH_RADIUS * math.asin(math.sqrt(h))
dist = [ [ haversine(a, b) for b in coordinates ] for a in coordinates ]
n = len(coordinates)
discrete = ll.PMedian(3, dist, [0] * n, contDemands, False, True)
discrete.solve()
check('contpmedian <= discrete pmedian', ll.ContPMedian(3, coordinates, contDemands), discrete.getObjValue(), heuristic=True)
discrete = ll.PCentre(3, dist, [0] * n, [1] * n, False, False)
discrete.solve()
check('contpcentre <= discrete pcentre', ll.ContPCentre(3, coordinates), discrete.getObjValue(), heuristic=True)

print('== errors')
checkException('mincostflow unbalanced', lambda: ll.MinCostFlow(edges, [4, 4, 2, 2, 1], supplies, [0, 0, 5, 14]))
checkException('maxflow unbounded', lambda: ll.MaxFlow(edges, 0, 3, ['M'] * 5))
checkException('maxflow parallel edges', lambda: ll.MaxFlow([[0, 1], [0, 1]], 0, 1, [3, 7]))
checkException('contpmedian capacity too small', lambda: ll.ContPMedian(3, coordinates, contDemands, capacities=10))
checkException('contpcentre two hemispheres', lambda: ll.ContPCentre(1, [[0, 0], [0, 120], [0, -120]]))


print(f'== {nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

""" regression test of the pyLogisticsLab models - the same problems as tests/serverTests/checkServer.py

    python tests/pyCmpl/checkLibrary.py
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

# node capacities and unequal totals of supply and demand (balance auto)
check('mincostflow node capacity, supply surplus',
      ll.MinCostFlow(edges, [4, 4, 2, 2, 1], [25, 0, 0, 0], [0, 0, 5, 15], nodeMaxCaps=[None, 12, None, None],
                     balance='auto'), 95)
check('multimodal node capacity, demand surplus with shortage costs',
      ll.MultiModalFlow(edges, [[4, 1], [4, None], [2, None], [2, 1], [1, None]], [20, 0, 0, 0], [0, 0, 10, 15],
                        nodeMaxCaps=[None, None, 8, None], balance='auto', shortageCosts=[0, 0, 0, 100]), 45)
check('multicommodity balance auto per commodity',
      ll.MultiCommodityFlow(edges, [[4, 1], [4, 1], [2, 1], [2, 1], [1, 1]], [[10, 5], [0, 0], [0, 0], [0, 0]],
                            [[0, 0], [0, 0], [0, 0], [8, 7]], maxCaps=[15, 8, 20, 'M', 10], balance='auto'), 50)
check('mincostflow unbalanced, default balance auto', ll.MinCostFlow(edges, [4, 4, 2, 2, 1], [25, 0, 0, 0], demands,
                                                                     maxCaps=maxCaps), 114)
check('maxflow node capacity', ll.MaxFlow(edges, 0, 3, maxCaps, nodeMaxCaps=[None, None, 6, None]), 11)
# node capacity with capacity factors per commodity (one unit of commodity 0 uses 2) = the node 2 split by hand
# into 2 (in) and 4 (out), the edge 2 -> 4 with the capacity and the factors; with factor 1 the value is 62
mcCosts = [[4, 1], [4, 1], [2, 1], [2, 1], [1, 1]]
mcSupplies, mcDemands = [[10, 5], [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [10, 5]]
check('multicommodity node capacity with capacity factors',
      ll.MultiCommodityFlow(edges, mcCosts, mcSupplies, mcDemands, maxCaps=[15, 8, 20, 'M', 10],
                            nodeMaxCaps=[None, None, 10, None], nodeCapacityFactors=[[1, 1], [1, 1], [2, 1], [1, 1]]),
      65)
# the LP of a multi-commodity flow is not integral (2.5 / 7.5 units), isInteger gives integer flows (MIP)
check('multicommodity LP not integral',
      ll.MultiCommodityFlow(edges, mcCosts, mcSupplies, mcDemands, maxCaps=[15, 8, 20, 'M', 10],
                            nodeMaxCaps=[None, None, 15, None], nodeCapacityFactors=[[1, 1], [1, 1], [2, 1], [1, 1]]),
      62.5)
check('multicommodity isInteger',
      ll.MultiCommodityFlow(edges, mcCosts, mcSupplies, mcDemands, maxCaps=[15, 8, 20, 'M', 10],
                            nodeMaxCaps=[None, None, 15, None], nodeCapacityFactors=[[1, 1], [1, 1], [2, 1], [1, 1]],
                            isInteger=True), 63)
check('multicommodity node capacity with capacity factors = split by hand',
      ll.MultiCommodityFlow([[0, 1], [0, 2], [1, 2], [1, 3], [4, 3], [2, 4]], mcCosts + [[0, 0]],
                            mcSupplies + [[0, 0]], mcDemands + [[0, 0]], maxCaps=[15, 8, 20, 'M', 10, 10],
                            capacityFactors=[[1, 1]] * 5 + [[2, 1]]), 65)

print('== multi-stage warehouse location (book example WLP-Mehrstufig: plants -> central -> regional warehouses -> customers)')
# edges from-to:cost rate:capacity, warehouses node:opening costs:capacity, sources and sinks node:supply:demand
msNodes = ['H', 'W1', 'W2', 'W3', 'Z1', 'Z2', 'Z3', 'R1', 'R2', 'R3', 'R4', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7']
msEdges = [ (msNodes.index(a), msNodes.index(b), float(c), float(k)) for e in """H-Z1:25:340 H-Z2:45:340 H-Z3:60:340 W1-Z1:12:340 W1-Z2:50:340 W1-Z3:36:340 W2-Z1:110:340 W2-Z2:62:340 W2-Z3:54:340 W3-Z1:30:340 W3-Z2:24:340 W3-Z3:28:340 Z1-R1:15:600 Z1-R2:18:600 Z1-R3:24:600 Z1-R4:20:600 Z2-R1:28:600 Z2-R2:30:600 Z2-R3:22:600 Z2-R4:12:600 Z3-R1:22:600 Z3-R2:14:600 Z3-R3:16:600 Z3-R4:8:600 R1-D1:60:340 R1-D2:52:340 R1-D3:70:340 R1-D4:60:340 R1-D5:40:340 R2-D2:84:340 R2-D3:15:340 R2-D4:28:340 R2-D6:42:340 R2-D7:120:340 R3-D2:72:340 R3-D3:42:340 R3-D4:18:340 R3-D5:30:340 R3-D6:50:340 R3-D7:60:340 R4-D2:74:340 R4-D4:45:340 R4-D5:20:340 R4-D7:110:340""".split()
            for (a, b), c, k in [ (e.split(':')[0].split('-'), *e.split(':')[1:]) ] ]
msWh = { n: (float(f), float(k)) for n, f, k in (w.split(':') for w in "Z1:25000:600 Z2:20000:600 Z3:20000:600 R1:25000:450 R2:20000:450 R3:15000:450 R4:20000:450".split()) }
msSD = { n: (float(s), float(dd)) for n, s, dd in (x.split(':') for x in "H:320:0 W1:500:0 W2:260:0 W3:120:0 D1:0:120 D2:0:240 D3:0:80 D4:0:280 D5:0:160 D6:0:180 D7:0:140".split()) }

def multiStage(isSingleSource=False):
    return ll.MultiStageWlp([ [a, b] for a, b, _, _ in msEdges ], [ c for _, _, c, _ in msEdges ],
                            [ msSD.get(n, (0, 0))[0] for n in msNodes ], [ msSD.get(n, (0, 0))[1] for n in msNodes ],
                            nodeFixedCosts=[ msWh.get(n, (0, None))[0] for n in msNodes ],
                            nodeMaxCaps=[ msWh.get(n, (0, None))[1] for n in msNodes ],
                            maxCaps=[ k for _, _, _, k in msEdges ], isSingleSource=isSingleSource, balance='exact')

def multiStageSplit():
    """ the warehouses split by hand into in and out node with the fixed costs on the edge in -> out (as in Excel) """
    names = msNodes + [ n + "'" for n in msWh ]
    out = { n: names.index(n + "'") for n in msWh }
    edges = [ [out.get(msNodes[a], a), b] for a, b, _, _ in msEdges ] + [ [msNodes.index(n), out[n]] for n in msWh ]
    return ll.MinCostFlow(edges, [ c for _, _, c, _ in msEdges ] + [0] * len(msWh),
                          [ msSD.get(n, (0, 0))[0] for n in names ], [ msSD.get(n, (0, 0))[1] for n in names ],
                          maxCaps=[ k for _, _, _, k in msEdges ] + [ msWh[n][1] for n in msWh ],
                          fixedCosts=[0] * len(msEdges) + [ msWh[n][0] for n in msWh ], balance='exact')

check('multistagewlp = book example (Excel)', multiStage(), 208410)
check('multistagewlp = min cost flow with the warehouses split by hand', multiStageSplit(), 208410)
check('multistagewlp single source', multiStage(True), 230200)

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
checkException('mincostflow unbalanced with balance exact',
               lambda: ll.MinCostFlow(edges, [4, 4, 2, 2, 1], supplies, [0, 0, 5, 14], balance='exact'))
checkException('maxflow unbounded', lambda: ll.MaxFlow(edges, 0, 3, ['M'] * 5))
checkException('maxflow parallel edges', lambda: ll.MaxFlow([[0, 1], [0, 1]], 0, 1, [3, 7]))
checkException('mincostflow wrong balance', lambda: ll.MinCostFlow(edges, [4, 4, 2, 2, 1], supplies, demands, balance='x'))
checkException('multimodal minimal node capacities', lambda: ll.MultiModalFlow(
    edges, [[1], [1], [1], [1], [1]], supplies, demands, nodeMinCaps=[0, 5, 0, 0]))
checkException('contpmedian capacity too small', lambda: ll.ContPMedian(3, coordinates, contDemands, capacities=10))
checkException('contpcentre two hemispheres', lambda: ll.ContPCentre(1, [[0, 0], [0, 120], [0, -120]]))


print(f'== {nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

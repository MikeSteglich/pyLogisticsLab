import pyLogisticsLab as ll

import sys
import traceback


# network: nodes 0..3, edges (i, j) - node 0 supplies 20 units, nodes 2 and 3 demand 5 and 15
edges = [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]]
supplies = [20, 0, 0, 0]
demands = [0, 0, 5, 15]


try:
    print('== min cost flow (CMPL)')
    m = ll.MinCostFlow(edges, costs=[4, 4, 2, 2, 1], supplies=supplies, demands=demands, maxCaps=[15, 8, 20, 5, 10])
    m.solve()
    if m.isSolution():
        print('obj   ', m.getObjValue())
        print('flows ', m.getFlows())

    print('== min cost flow with fixed costs (CMPL) - edge 1-3 is too expensive, the flow goes via 2-3')
    m = ll.MinCostFlow(edges, costs=[4, 3, 2, 2, 1], supplies=supplies, demands=demands, maxCaps=[15, 15, 20, 10, 15],
                       fixedCosts=[10, 60, 10, 30, 10])
    m.solve()
    if m.isSolution():
        print('obj   ', m.getObjValue(), '(variable', m.getVarCosts(), '+ fixed', m.getFixedCosts(), ')')
        print('flows ', m.getFlows())
        print('usages', m.getUsages())

    print('== maximal flow from 0 to 3 (CMPL)')
    m = ll.MaxFlow(edges, source=0, sink=3, maxCaps=[15, 8, 20, 5, 10])
    m.solve()
    if m.isSolution():
        print('obj   ', m.getObjValue())
        print('flows ', m.getFlows())

    print('== multi-commodity flow, 2 commodities with joint capacities (CMPL)')
    m = ll.MultiCommodityFlow(edges,
                              costs=[[4, 1], [4, 1], [2, 1], [2, 1], [1, 1]],
                              supplies=[[10, 5], [0, 0], [0, 0], [0, 0]],
                              demands=[[0, 0], [0, 0], [0, 0], [10, 5]],
                              maxCaps=[15, 8, 20, 'M', 10])
    m.solve()
    if m.isSolution():
        print('obj   ', m.getObjValue())
        print('flows ', m.getFlows())

    print('== multi-modal flow, truck and train with fixed costs (CMPL)')
    m = ll.MultiModalFlow(edges,
                          costs=[[4, 1], [4, None], [2, None], [2, 1], [1, None]],      # None: no train on this edge
                          supplies=supplies, demands=demands,
                          fixedCosts=[[0, 30], [0, 0], [0, 0], [0, 30], [0, 0]],
                          minCaps=[[0, 10], [0, 0], [0, 0], [0, 10], [0, 0]])          # train only from 10 units
    m.solve()
    if m.isSolution():
        print('obj   ', m.getObjValue(), '(variable', m.getVarCosts(), '+ fixed', m.getFixedCosts(), ')')
        print('flows ', m.getFlows())
        print('usages', m.getUsages())

except ll.LogLabException as e:
    print(e)
except:
    traceback.print_exc()

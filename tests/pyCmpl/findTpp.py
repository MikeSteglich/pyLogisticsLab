import pyLogisticsLab as ll

import sys
import traceback


varCosts = [[3, 2, 7, 6],
            [7, 5, 2, 3],
            [2, 5, 4, 5]]

supplies = [5000, 6000, 2500]
demands = [6000, 4000, 2000, 1500]


try:
    m = ll.Tpp(varCosts, supplies, demands, objSense='min')

    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        flows = m.getFlows()
        sourceFlows = m.getSourceFlows()
        destFlows = m.getDestinationFlows()

except ll.LogLabException as e:
    tppOK = False
    tppMsg = e
    print(e)
except:
    tppOK = False
    tppMsg = str(sys.exc_info())
    traceback.print_exc()
else:
    tppOK = True
    tppMsg = "OK"

    print (tppMsg)

    print('obj ', objVal)
    print('flows ', flows)
    print('sourceFlows ', sourceFlows)
    print('destFlows ', destFlows)

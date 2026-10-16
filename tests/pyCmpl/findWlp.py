
import pyLogisticsLab as ll

import sys
import traceback


varCosts =  [[1395.05,2120.10,1296.03,1800.63,2225.04,2603.57,2444.97, 472.49,2584.60,1865.76,2094.30, 401.82],
 [581.15, 628.42, 914.77, 164.76,1578.24,1956.77,1417.19,1412.87,1712.85, 525.62, 562.96,1896.85],
 [797.80, 802.42, 727.15,1326.30, 369.36, 901.84, 490.93,1568.77, 630.57,1728.19, 925.97,2052.75]]

fixedCosts = [800000, 1000000, 1200000]

supplies = [3800, 4000, 4200]
demands= [900, 1100, 1300, 700, 1000, 1000, 800, 900, 1200, 1100, 1000, 1000]

isCap = True


try:
    m =ll.Wlp( varCosts, fixedCosts, supplies, demands, isCap)

    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        activeSources = m.getActiveSources()
        destSourceMapping = m.getDestSourceMapping()

except ll.LogLabException as e: 
    wlpOK = False
    wlpMsg = e
    #traceback.print_exc()
    print(e)
except:
    wlpOK = False
    wlpMsg = str(sys.exc_info())
    traceback.print_exc()
else:
    wlpOK = True
    wlpMsg = "OK" 

    print (wlpMsg)
 
    print('obj ',objVal)
    print('activeSources ',activeSources)
    print('destSourceMapping ',destSourceMapping)
import pyLogisticsLab as ll
import sys
import traceback

'''nrOfSources = 4
nrOfDests = 6
varCosts = [[19,75,42,11,52,63],
            [46,109,41,8,34,38],
            [47,65,29,14,17,18],
            [71,64,14,24,22,33]  ]
fixedCosts = [30,40,70,40]  
radius = 65
maxCost = 65'''

nrOfSources = 3
nrOfDests = 7
varCosts = [[ 102.55, 205.81,216.74, 222.25, 203.35,258.88,234.88],
          [  95.32, 220.83,249.34,230.33,247.07,232.53, 236.88],
          [102.08, 203.89, 224.68,220.18, 215.40,256.53, 232.68]]

demands = [170,225,100,110,120,75,80]

fixedCosts = [1000000,500000,2000000]  
radius = 233
maxCost = 1500000


try:         
    m =ll.Mcp( varCosts, radius, maxCost, demands)
    m.setFixedCosts(fixedCosts)
    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        activeSources = m.getActiveSources()
        destSourceMapping = m.getDestSourceMapping()
        destSourceMappingSingleSource = m.getDestSourceMappingSingleSource()
    else:
        mcpOk=False
        mcpMsg= 'No solution has beeen found'

except ll.LogLabException as e: 
    mcpOK = False
    mcpMsg = e
    traceback.print_exc()
except:
    mcpOK = False
    mcpMsg = str(sys.exc_info())
    traceback.print_exc()
else:
    mcpOK = True
    mcpMsg = "OK" 

    print (mcpMsg)
 
    print('obj ',objVal)
    print('activeSources ',activeSources)
    print('destSourceMapping ',destSourceMapping)
    print('destSourceMappingSingleSource ',destSourceMappingSingleSource)
    

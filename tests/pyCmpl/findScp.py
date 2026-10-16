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
radius = 65'''


varCosts = [[ 102.55, 205.81,216.74, 222.25, 203.35,258.88,234.88],
          [  95.32, 220.83,249.34,230.33,247.07,232.53, 236.88],
          [102.08, 203.89, 224.68,220.18, 215.40,256.53, 232.68]]

fixedCosts = [1000000,500000,2000000]  
radius = 233


try:  
    m =ll.Scp( varCosts, radius)
    m.setFixedCosts(fixedCosts)
    m.solve()
    if m.isSolution():
        objVal = m.getObjValue()
        activeSources = m.getActiveSources()
        destSourceMapping = m.getDestSourceMapping()
        destSourceMappingSingleSource = m.getDestSourceMappingSingleSource()
    else:
        objVal=-1
        scpMsg= 'No solution has beeen found'

except ll.LogLabException as e: 
    print(e)
    traceback.print_exc()
except:
    scpMsg = str(sys.exc_info())
    traceback.print_exc()
else:
    if objVal>=0:
        print('obj ',objVal)
        print('activeSources ',activeSources)
        print('destSourceMapping ',destSourceMapping)
        print('destSourceMappingSingleSource ',destSourceMappingSingleSource)
    else:
        print('No solution has been found')
    

from .tools import *
from .exception import *

from pyCmpl import *
import os
import tempfile
import shutil
import pathlib



#*************** CmplMcp  ************************************************
class Mcp(object):

    #*********** constructor **********
    def __init__(self, distCostMatrix, radius, maxSrcCost, demands, mipGap=0.00, maxSolvingTime=30):
        
        self.__model = None
   
        self.__distCostMatrix = setDistMatrix(distCostMatrix)
        self.__nrOfSources = len(self.__distCostMatrix)
        self.__nrOfDestinations = len(self.__distCostMatrix[0])

        self.__fixedCosts = [ 1 for a in range(self.__nrOfSources) ]

        self.__maxSolvingTime = setMaxSolvingTime(maxSolvingTime)
        self.__mipGap = setMipGap(mipGap)

        self.__demands = setNumVector(demands)

        self.__maxSrcCost = setNum(maxSrcCost)
       
        self.__coveringMatrix = coveringMatrix(self.__distCostMatrix, radius)
    
        self.__totalSupply = 0
        self.__activeSources = [ 0  for a in range(self.__nrOfSources)  ]
        self.__destSourceMappingSingleSource =  [ -1  for _ in range(self.__nrOfDestinations)  ]
        self.__destSourceMapping =  [ []   for a in range(self.__nrOfDestinations)  ]

        self.solutionStatus = False
        
        self.__modelName=str(pathlib.Path(__file__).parent.absolute())+os.sep+'Mcp.cmpl'
        self.__tmpPath = tempfile.gettempdir()+os.sep
        
    #*********** end constructor ******
    

    def setFixedCosts(self, fixedCosts):
        self.__fixedCosts = setNumVector(fixedCosts, self.__nrOfSources) 

    def getObjValue(self):
        return self.__totalSupply

    def getActiveSources(self):
        return self.__activeSources

    def getDestSourceMappingSingleSource(self):
        return self.__destSourceMappingSingleSource

    def getDestSourceMapping(self):
        return self.__destSourceMapping

    def isSolution(self):
        return self.solutionStatus


    #*********** solve ************
    def solve(self):
        src = CmplSet("Sources")
        src.setValues(1,self.__nrOfSources )
        
        dest = CmplSet("Destinations")
        dest.setValues(1,self.__nrOfDestinations)
        
        a = CmplParameter("a", src, dest )
        a.setValues(self.__coveringMatrix)
                
        f =  CmplParameter("f",src)    
        f.setValues(self.__fixedCosts)

        d = CmplParameter("d",dest)    
        d.setValues(self.__demands)

        p =  CmplParameter("p" )
        p.setValues(self.__maxSrcCost)
                                   
        shutil.copyfile(self.__modelName, self.__tmpPath+"Mcp.cmpl") 
        modelName=self.__tmpPath+"Mcp.cmpl" 

        self.__model = Cmpl(modelName)

        self.__model.setSets(src,dest)

        self.__model.setParameters( a, f, d, p )

    
        #self.__model.debug()
        self.__model.setOutput(False)

        #self.__model.setOption('-solver scip')   
        #self.__model.setOption(f'-opt scip limits/time={timeLimit}')   

        self.__model.setOption('-solver highs')   
        self.__model.setOption(f'-opt highs time_limit={self.__maxSolvingTime}') 
        if self.__mipGap>0:
            self.__model.setOption(f'-opt highs mip_rel_gap={self.__mipGap}') 
               
        #self.__model.debug()
        self.__model.solve()
              
        if self.__model.solverStatus == SOLVER_OK:
            
            self.__totalSupply = self.__model.solution.value

            if self.__model.solution.value == 0:
                  raise McpException('No solution has been found')

            self.solutionStatus = True

            for i in src.values:
                try:
                    if self.__model.x[i].activity == 1:
                        self.__activeSources[i-1] = 1
                except:
                    pass
            
            for j in dest.values:
                for i in src.values:
                    if self.__activeSources[i-1] == 1 and self.__coveringMatrix[i-1][j-1]==1:
                        self.__destSourceMapping[j-1].append(i)
            
                minDist=1000000000
                minIdx=-1
                for i in self.__destSourceMapping[j-1]:
                    if self.__distCostMatrix[i-1][j-1]<minDist:
                        minDist=self.__distCostMatrix[i-1][j-1]
                        minIdx=i
                self.__destSourceMappingSingleSource[j-1]=minIdx
        else:
            raise McpException('No solution has been found')
    #*********** end solve **************
    

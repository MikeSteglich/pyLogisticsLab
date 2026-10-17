from .tools import *
from .exception import *

from pyCmpl import *
import os
import shutil
import tempfile
import pathlib
import time
import logging

logger = logging.getLogger(__name__)

#*************** PMedian  ************************************************
class PCentre(object):

    #*********** constructor **********
    def __init__(self, p, varCosts, supplies,demands, isCap, isDemandWeighted, mipGap=0.001, maxSolvingTime=10):
              
        self.__model = None
        if isCap:
            self.__isCap = 1
        else:
            self.__isCap = 0

        if isDemandWeighted:
            self.__isDemandWeighted = 1
        else:
            self.__isDemandWeighted = 0

        self.__maxSolvingTime = setMaxSolvingTime(maxSolvingTime)
        self.__mipGap = setMipGap(mipGap)

        self.__varCosts = setNumMatrix(varCosts)
        self.__nrOfSources = len(self.__varCosts)
        self.__nrOfDestinations = len(self.__varCosts[0])
        self.__p = p

        self.__NodeHeuristics = 100
        self.__debug = False

        self.__nrOfNodes = self.__nrOfDestinations + self.__nrOfDestinations

        if self.__mipGap==0:
            if self.__nrOfNodes < 50:
                self.__mipGap = 0.001
            elif self.__nrOfNodes < 100:
                self.__mipGap = 0.02
            elif self.__nrOfNodes < 150:
                self.__mipGap = 0.03
            else:
                self.__mipGap = 0.05
        
        self.__edges = []
        self.__vCosts = []

        self.__costTolAdder = 0
        self.__maxCostSrc = []
        self.__minCostSrc = []
        self.__avgCostSrc = []
        self.__costTolSrc = []

        for c in self.__varCosts:        
            self.__minCostSrc.append(min(c))
            self.__maxCostSrc.append(max(c))
            avgCost = sum(c)/self.__nrOfDestinations
            self.__avgCostSrc.append(avgCost)

        self.__supplies = setNumVector(supplies)  
        self.__demands = setNumVector(demands)  
        
        self.__totalCosts = 0
        self.__activeSources = [ 0  for a in range(self.__nrOfSources)  ]
        self.__destSourceMapping =  [ -1  for a in range(self.__nrOfDestinations)  ]

        self.solutionStatus = False
        self.__modelName=str(pathlib.Path(__file__).parent.absolute())+os.sep+'pCentre.cmpl'
        self.__tmpPath = tempfile.gettempdir()+os.sep
        
    #*********** end constructor ******
    
    def getObjValue(self):
        return self.__totalCosts

    def getActiveSources(self):
        return self.__activeSources

    def getDestSourceMapping(self):
        return self.__destSourceMapping

    def isSolution(self):
        return self.solutionStatus

     #*********** end readTppFile ************       

    def __setCostTol(self):
        factor = 1.25
        for i in range(self.__nrOfSources):  
            if self.__avgCostSrc[i] > self.__minCostSrc[i]:
                self.__costTolSrc.append( self.__avgCostSrc[i]/self.__maxCostSrc[i] * factor)
            else: 
                self.__costTolSrc.append( self.__minCostSrc[i]/self.__maxCostSrc[i] * factor )


    
    #*********** __setEdges     ************
    def __setEdges(self ):

        destInEdges = [ False for d in range(self.__nrOfDestinations)]

        while True:
            self.__edges = []
            self.__vCosts = []
                
            for i in range(self.__nrOfSources):
                self.__costTolSrc[i] += self.__costTolAdder
                maxCost = self.__maxCostSrc[i] * self.__costTolSrc[i] 

                for j in range(self.__nrOfDestinations):
                    if self.__isCap:
                        if self.__varCosts[i][j] <= maxCost and self.__varCosts[i][j]<bigM:
                            self.__edges.append((i+1,j+1))
                            self.__vCosts.append(self.__varCosts[i][j]) 
                            destInEdges[j] = True
                    else:
                        self.__edges.append((i+1,j+1))
                        self.__vCosts.append(self.__varCosts[i][j]) 
                        destInEdges[j] = True
            if not False in destInEdges:
                break
            else:
                self.__costTolAdder += 0.1 
    #*********** __setEdges     ************    
    
    #*********** __fixVariables  ************

    def __fixVariables(self):
        self.__fixedEdges = []

        for i,j in self.__edges:
            try:
                if self.__model.x[(i,j)].activity == 0:
                    if random.random()<self.__fixVarProb:
                        self.__fixedEdges.append((i,j))
       
            except Exception as err:
                raise LogLabException("Error while fixing vars <" +str( err)+">" )

    def __checkCostTol(self):
        ok = False
        for tol in self.__costTolSrc:
            if tol < 1:
                ok = True
        return ok
    
    #*********** solve ************
    def solve(self):

        maxTries = 5
        tries = 1
        sTime=time.time()

        w = CmplSet("sources")
        w.setValues(1,self.__nrOfSources )
        
        c = CmplSet("destinations")
        c.setValues(1,self.__nrOfDestinations)

        self.__costTolAdder = 0
        self.__setCostTol()
        
        p =  CmplParameter("p")    
        p.setValues(self.__p)
               
        cap =  CmplParameter("s",w)    
        cap.setValues(self.__supplies)
            
        dem =  CmplParameter("d",c)    
        dem.setValues(self.__demands)

        isCap = CmplParameter('isCap')
        isCap.setValues(self.__isCap)

        isDemandWeighted = CmplParameter("isDemandWeighted")
        isDemandWeighted.setValues(self.__isDemandWeighted)

        edges = CmplSet("edges",2)

        self.__fixedEdges= [(-1,-1)]
        fEdges = CmplSet("fixedEdges",2)
        fEdges.setValues(self.__fixedEdges )

        costs = CmplParameter("c", edges )
     
        isRelaxed = CmplParameter('isRelaxed')

        shutil.copyfile(self.__modelName, self.__tmpPath+"pCentre.cmpl") 
        modelName=self.__tmpPath+"pCentre.cmpl" 

        self.__fixVarProb = 0.4

        while True:
            if self.__nrOfNodes > self.__NodeHeuristics:
                while True:
            
                    self.__setEdges()
                    edges.setValues(self.__edges)
                           
                    costs.setValues(self.__vCosts)

                    isRelaxed.setValues(1)
            
                    self.__model = Cmpl(modelName)

                    self.__model.setSets(fEdges, edges,w,c)
                    self.__model.setParameters(costs, p, cap, dem, isCap, isDemandWeighted, isRelaxed)
            
                    self.__model.debug(self.__debug )
                    #self.__model.setOutput(False)

                    self.__model.setOption('-solver highs')   
                    self.__model.setOption(f'-opt highs time_limit={self.__maxSolvingTime}')   
                    #self.__model.setOption('-solver scip')   
                    #self.__model.setOption(f'-opt scip limits/time={elf.__maxSolvingTime}')   

                    logger.info('    ... solving relaxtion ')
               
                    self.__model.solve()
                              
                    if self.__model.solverStatus == SOLVER_OK:
            
                        self.__totalCosts = self.__model.solution.value
                        self.solutionStatus = True

                        for i in w.values:
                            try:
                                if self.__model.y[i].activity == 1:
                                    self.__activeSources[i-1] = 1
                        
                                for j in c.values:
                                    try:
                                        if self.__model.x[(i,j)].activity > 0:
                                            self.__destSourceMapping[j-1] = i
                                    except:
                                        pass
                            except:
                                pass
                        logger.info(f'        ... Solution has been found with obj value {self.__model.solution.value} ')
                        break
                    else:
                        logger.info('        ... No solution has been found')
                        if not self.__checkCostTol():
                            raise LogLabException(' No solution has been found with relaxation - checkTol')
                  
                        self.__costTolAdder += 0.1
                        self.__setCostTol()

                        if (time.time()-sTime) > self.__maxSolvingTime:
                            raise LogLabException(' No solution has been found with relaxation ')

                        #raise LogLabException(' No solution has been found with relaxation')

                logger.info('    ... solving fixed model ')

                self.__fixVariables()
            
            else:
                self.__edges = []
                self.__vCosts  = []
        
                for i in range(self.__nrOfSources):
                    for j in range(self.__nrOfDestinations):
                        self.__edges.append((i+1,j+1))
                        self.__vCosts.append(self.__varCosts[i][j]) 

                edges.setValues(self.__edges)
                costs.setValues(self.__vCosts)
                    
            self.__model = Cmpl(modelName)

            fEdges.setValues(self.__fixedEdges )
            isRelaxed.setValues(0)

            if  (time.time()-sTime) > self.__maxSolvingTime:
                raise LogLabException(' No solution has been found')

            self.__model.setOption('-solver highs')   
            self.__model.setOption(f'-opt highs time_limit={self.__maxSolvingTime}')  
            self.__model.setOption(f'-opt highs mip_rel_gap={self.__mipGap}')  
            #self.__model.setOption('-solver scip')   
            #self.__model.setOption(f'-opt scip limits/time={self.__maxSolvingTime}')   
            
            self.__model.setSets(fEdges, edges,w,c)
            self.__model.setParameters(costs, p, cap, dem, isCap, isDemandWeighted, isRelaxed)

            self.__model.debug(self.__debug )
            self.__model.solve()  
  
            if self.__model.solverStatus == SOLVER_OK:
            
                self.__totalCosts = self.__model.solution.value
                self.solutionStatus = True

                for i in w.values:
                    try:
                        if self.__model.y[i].activity == 1:
                            self.__activeSources[i-1] = 1
                        
                        for j in c.values:
                            try:
                                if self.__model.x[(i,j)].activity > 0:
                                    self.__destSourceMapping[j-1] = i
                            except:
                                pass
                    except:
                        pass
                break
            else:
                logger.info('    ... No solution has been found after '+ str(tries) + ' tries')
                self.__costTolAdder += 0.05
                self.__setCostTol()
                self.__fixVarProb -= 0.1
                if self.__fixVarProb < 0:
                    self.__fixVarProb=0
                tries += 1
                logger.info(f'    ... new try with fixVarProb: {self.__fixVarProb}')
                if tries > maxTries or  (time.time()-sTime) > self.__maxSolvingTime:
                    raise LogLabException(' No solution has been found after '+ str(tries) + ' tries')
                

        
    #*********** end solve **************
    

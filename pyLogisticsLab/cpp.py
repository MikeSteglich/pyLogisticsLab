from .tools import *
from .exception import *

from pyCmpl import *
import os
import tempfile
import shutil
import pathlib
import logging

logger = logging.getLogger(__name__)



#*************** CmplCPP  ************************************************
class Cpp(object):
        
        #*********** constructor **********
        def __init__(self, edges, edgeTypes, edgeWeights, startNode, mipGap=0.0, maxSolvingTime=30):

            self.__edges = []
            self.__edgeTypes = []
            self.__edgeWeights = []
            self.__edgeUsages = []

            self.__origEdgeIndices = {}

            self.__Nodes = []

            self.__setStartNode(startNode)
            self.__setEdges(edges, edgeTypes, edgeWeights)
            
            self.__maxSolvingTime = setMaxSolvingTime(maxSolvingTime)
            self.__mipGap = setMipGap(mipGap)

            self.__eulerTour = []
            self.__edgesUsed = []
            self.__objVal = 0
                                
            self.__model= None
            self.__modelName=str(pathlib.Path(__file__).parent.absolute())+os.sep+'cpp.cmpl'
            self.__solutionStatus = False

            self.__tmpPath = tempfile.gettempdir()+os.sep
        #*********** end constructor ******
        
        
        def __setStartNode(self, sNode):
            if not isinstance(sNode,int):
                raise LogLabException(f'LogisticsLab error: Wrong start node {sNode}')
            else:
                self.__startNode = sNode 


        def __setEdges(self, edges, eTypes, eWeights):
            edges = setEdges(edges)

            self.__edgeUsages = [ 0 for i in range(len(edges))]

            tmpNodes=[]
            for idx, e in enumerate(edges):
                
                if  isinstance(eWeights[idx], (int, float)):
                    eWeight = eWeights[idx]
                else:
                    raise LogLabException(f'LogisticsLab error: Wrong weight of edge: {eWeights[idx]}' )

                if not isinstance(e, (list,tuple)):
                    raise LogLabException(f"LogisticsLab error: Wrong edge {e} " )

                if type(e)==list:
                    e=tuple(e)

                self.__origEdgeIndices[e] = idx
                
                if eTypes[idx]==0:
                    #directed edge
                    self.__edges.append(e)
                    self.__edgeTypes.append(0)
                    self.__edgeWeights.append(eWeight)
                    
                elif eTypes[idx]==1:
                    #undirected edge
                    self.__edges.append(e)
                    self.__edgeTypes.append(1)
                    self.__edgeWeights.append(eWeight)
                 
                    self.__edges.append( (e[1],e[0]) )
                    self.__edgeTypes.append(1)
                    self.__edgeWeights.append(eWeight)
                    
                else:
                    raise LogLabException(f'LogisticsLab error: Wrong type of edge: list or tuple expected instead of: {eTypes[idx]}' )
                tmpNodes.append(e[0])
                tmpNodes.append(e[1])

            self.__Nodes = list(set(tmpNodes))

       

        def __find_eulerian_tour(self, graph, s):

            while len(graph)>0:
                tour=[]
                if len(self.__eulerTour)==0:
                    i = graph.index(s)
                    self.__find_tour(graph[i][0],graph,tour)
                    self.__eulerTour=tour
                    
                else:
                    sNode = -1
                    for se in graph:
                        if se[0] in self.__eulerTour: 
                            sNode = se[0]
                        elif  se[0] in self.__eulerTour:
                            sNode = se[0]
                        if sNode!=-1:
                            break
                    self.__find_tour(sNode,graph,tour)
                    
                    s = tour[0]
                    i = self.__eulerTour.index(s)
                    self.__eulerTour.pop(i)
        
                    for j in range(0,len(tour)):
                        self.__eulerTour.insert(i+j,tour[j])

            if self.__eulerTour:
                self.__solutionStatus = True
            else:
                self.__solutionStatus = False
    
    
        def __find_tour(self, u,E,tour): 
            for (a,b) in E:
                if a==u:
                    E.remove((a,b))
                    self.__find_tour(b,E,tour)
            tour.insert(0,u)
  

        def getEulerTour(self):
            if self.__solutionStatus:
                return self.__eulerTour
            else:
                return []

        def isEulerTour(self):
            return self.__solutionStatus


        def getEdgeUsages(self):
            if self.__solutionStatus:
                return self.__edgeUsages
            else:
                return {}

        def getObjValue(self):
            return self.__objVal

        #*********** solve ************
        def solve(self):

            logger.info('Optimisation of CPP has been started')
            logger.info(' ... finding optimal number of edges to create an Euler network')
                    
            nodes = CmplSet("Nodes")
            nodes.setValues(self.__Nodes)
                                  
            arcs = CmplSet("Arcs",2)
            arcs.setValues(self.__edges)
                
            argWeights = CmplParameter("c", arcs )
            argWeights.setValues(self.__edgeWeights)
                
            arcTypes = CmplParameter("f", arcs )
            arcTypes.setValues(self.__edgeTypes)
                
            sNode = CmplParameter("s" )
            sNode.setValues(self.__startNode)
          
            shutil.copyfile(self.__modelName, self.__tmpPath+"cpp.cmpl") 
            modelName=self.__tmpPath+"cpp.cmpl" 
     
            self.__model = Cmpl(modelName)
                                        
            self.__model.setSets(nodes, arcs)
            self.__model.setParameters(argWeights,arcTypes,sNode)
                        
            #self.__model.debug()
            self.__model.setOutput(False)
                
            self.__model.setOption('-solver highs')   
            self.__model.setOption(f'-opt highs time_limit={self.__maxSolvingTime}')  

            if self.__mipGap>0:
                self.__model.setOption(f'-opt highs mip_rel_gap={self.__mipGap}') 

            self.__model.solve()

                
            self.__solutionStatus = ''

            logger.info(' ... done')
                
            if self.__model.solverStatus == SOLVER_OK:

                self.__objVal = self.__model.solution.value

                logger.info(' ... finding Euler tour')
                    
                sTuple = None
                
                for e in self.__edges:
                    nrOfUses = self.__model.x[e].activity
                
                    for i in range(nrOfUses):
                        self.__edgesUsed.append(e)

                    if sTuple == None:
                        if e[0]==self.__startNode:
                            if e in self.__edgesUsed:
                                sTuple=e
                    
                    if e in self.__origEdgeIndices:
                        idx = self.__origEdgeIndices[e]
                    else:
                        idx = self.__origEdgeIndices[ (e[1] , e[0]) ]   
                    self.__edgeUsages[idx] += nrOfUses          
       
                self.__find_eulerian_tour(self.__edgesUsed, sTuple )


                logger.info(' ... done')

                try:    
                    os.remove( modelName)
                except:
                    pass

            else:
                self.__solutionStatus = False
                logger.info(' ... No solution has been found')
                           
        #*********** end solve **************
                
        
#************** end Cpp  **********************************************





        
from .tools import *
from .exception import *

from pyCmpl import *
import os
import tempfile
import shutil
import pathlib



#*************** CmplCPP  ************************************************
class Nwf(object):
        
        #*********** constructor **********
        def __init__(self, nodeVolumes, nodeCapacities, edges, edgeWeights, minCap, maxCap, mipGap=0.0, maxSolvingTime=30):

            self.__nrOfNodes = len(nodeVolumes)

            self.__volumes = setNumVector(nodeVolumes)
            self.__capacities = setNumVector(nodeCapacities)
            if len(self.__capacities)!=self.__nrOfNodes:
                 raise LogLabException(f'LogisticsLab error: Nr. of capacities {len(self.__capacities)} unequal to nr. of nodes {self.__nrOfNodes}' )

            self.__edges = setEdges(edges, self.__nrOfNodes)
            self.__nrOfEdges=len(self.__edges)

            self.__edgeWeights = setNumVector(edgeWeights)
            if len(self.__edgeWeights)!=self.__nrOfEdges:
                 raise LogLabException(f'LogisticsLab error: Nr. of edges weights {len(self.__edgeWeights)} unequal to nr. of edges {self.__nrOfEdges}' )

            self.__edgeMinCap = setNumVector(minCap)
            if len(self.__edgeMinCap)!=self.__nrOfEdges:
                 raise LogLabException(f'LogisticsLab error: Nr. of minimum capacities of the edges  {len(self.__edgeMinCap)} unequal to nr. of edges {self.__nrOfEdges}' )

            self.__edgeMaxCap = setNumVector(maxCap)
            if len(self.__edgeMaxCap)!=self.__nrOfEdges:
                 raise LogLabException(f'LogisticsLab error: Nr. of maximum capacities of the edges  {len(self.__edgeMaxCap)} unequal to nr. of edges {self.__nrOfEdges}' )


            self.__edgeUsages = []

            self.__origEdgeIndices = {}

            self.__Nodes = []

          
            self.__setEdges(edges,edgeWeights)
            
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
        
        
     


        def __setEdges(self, edges, eWeights):
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

       

        def getEdgeUsages(self):
            if self.__solutionStatus:
                return self.__edgeUsages
            else:
                return {}

        def getObjValue(self):
            return self.__objVal

        #*********** solve ************
        def solve(self):

            print('Optimisation of CPP has been started')
            print(' ... finding optimal number of edges to create an Euler network')
                    
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

            self.__model.saveSolutionAscii()
                
            self.__solutionStatus = ''

            print(' ... done')
                
            if self.__model.solverStatus == SOLVER_OK:

                self.__objVal = self.__model.solution.value

                print(' ... finding Euler tour')
                    
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


                print(' ... done')

                try:    
                    os.remove( modelName)
                except:
                    pass

            else:
                self.__solutionStatus = False
                print(' ... No solution has been found')
                           
        #*********** end solve **************
                
        
#************** end Cpp  **********************************************





        
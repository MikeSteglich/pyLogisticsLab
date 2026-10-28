from .tools import *
from .exception import *

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import sys

ROUND_TRIP = 0
OPEN_BOTH_FIXED = 1
OPEN_FIXED_OPEN = 2
OPEN_OPEN_FIXED = 3
OPEN_BOTH_OPEN = 4


class TspMaster():
    def __init__(self, distances, edges=None, startNode=0, endNode=None, openRoute=False):
        
        self.__num_vehicles = 1

        self.__nrOfNodes = len(distances)
        self.__startNode = self.__setStartEndNode(startNode)
        self.__endNode = self.__setStartEndNode(endNode)
        
        self.__isOpenRoute=openRoute
        if not self.__isOpenRoute:
            self.__routeMode = ROUND_TRIP
            if startNode!=None:
                self.__startNode = startNode
            else:
                self.__startNode=0
            self.__endNode = None

        else:
            if startNode!=None and endNode==None:
                self.__routeMode = OPEN_FIXED_OPEN
                self.__startNode = startNode
                self.__endNode = endNode

            elif startNode==None and endNode!=None:
                self.__routeMode = OPEN_OPEN_FIXED
                self.__startNode = [0]
                self.__endNode = [endNode+1]
                
            elif startNode!=None and endNode!=None:
                self.__routeMode = OPEN_BOTH_FIXED 
                self.__startNode = [startNode]
                self.__endNode = [endNode]
            
            elif startNode==None and endNode==None:
                self.__routeMode = OPEN_BOTH_OPEN
                self.__startNode = 0
                self.__endNode = None

        self.__edges=setEdges(edges, self.__nrOfNodes)

        self.__distance_matrix = self.__setDistances(distances)

        self.__manager=None
        self.__routing=None
        self.__solution = None
        self.__route = []

    def __setStartEndNode(self, seNode):
        """ checks and sets the start or end node """
        if seNode!=None:
            if not isinstance(seNode,int):
                raise LogLabException(f'LogisticsLab error: Wrong start or end node {seNode}')
            else:
                if seNode<0 or seNode>=self.__nrOfNodes:
                    raise LogLabException(f'LogisticsLab error: Wrong start node {seNode}')
        return seNode 
       
   
    def __setDistances(self, distances):
        """ defines the distance matrix for the differend TSP variants"""
        
        # a copy - the variants below change the rows
        distance_matrix=[ list(row) for row in setDistMatrix(distances) ]

        if self.__edges:
            # the edges as tuples - they come as lists from JSON ([a, b] != (a, b)); a connection that is no edge gets
            # a value longer than any tour over the edges
            arcs = { (int(e[0]), int(e[1])) for e in self.__edges }
            n = len(distance_matrix)
            longest = max((v for row in distance_matrix for v in row), default=0)
            bigM = max(1, longest) * (n + 1)
            for i in range(n):
                for j in range(n):
                    if i != j and (i,j) not in arcs:
                        distance_matrix[i][j] = bigM
           
        if self.__routeMode == OPEN_FIXED_OPEN:
            for row in distance_matrix:
                row[self.__startNode]=0
        elif self.__routeMode == OPEN_OPEN_FIXED:
            tempDistMatrix = [ None for _ in range(len(distance_matrix)+1) ]
            tempDistMatrix[0] = [ 0 for _ in range(len(distance_matrix)+1)]
            for i,row in  enumerate(distance_matrix):
                if (i+1) == self.__endNode[0]:
                    tempDistMatrix[i+1] = [ 0 for _ in range(len(distance_matrix)+1)]
                else:
                    tempDistMatrix[i+1] = row
                    tempDistMatrix[i+1].insert(0,0)
            distance_matrix=tempDistMatrix
        elif self.__routeMode == OPEN_BOTH_OPEN:
            tempDistMatrix = [ None for _ in range(len(distance_matrix)+1) ]
            tempDistMatrix[0] = [ 0 for _ in range(len(distance_matrix)+1)]
            for i,row in  enumerate(distance_matrix):
                tempDistMatrix[i+1] = row
                tempDistMatrix[i+1].insert(0,0)
            distance_matrix=tempDistMatrix

        return distance_matrix


    def isSolution(self):
        """Returns whether a solution exists"""
        if self.__solution:
            return True
        else:
            return False

    def solution(self):
        """Returns the solution as tuple (objValue, Route)"""
        if self.__solution:
            index = self.__routing.Start(0)
            while not self.__routing.IsEnd(index):
               
                if self.__routeMode != OPEN_OPEN_FIXED and self.__routeMode != OPEN_BOTH_OPEN:
                    self.__route.append(self.__manager.IndexToNode(index))
                else:
                    if index!=0:
                       self.__route.append(self.__manager.IndexToNode(index)-1) 

                index = self.__solution.Value(self.__routing.NextVar(index))

            if self.__routeMode == ROUND_TRIP or self.__routeMode == OPEN_BOTH_FIXED :
                self.__route.append(self.__manager.IndexToNode(index)) 
            elif self.__routeMode == OPEN_OPEN_FIXED: 
                self.__route.append(self.__manager.IndexToNode(index)-1) 

            return self.__solution.ObjectiveValue(),self.__route
        else:
            return None,None

    def __distance_callback(self, from_index, to_index):
        """Returns the distance between the two nodes."""
        from_node = self.__manager.IndexToNode(from_index)
        to_node = self.__manager.IndexToNode(to_index)
        return self.__distance_matrix[from_node][to_node]

    def solve(self):    
        """Solves the problem"""
        self.__solution=None
        try:

            if self.__routeMode == ROUND_TRIP or self.__routeMode == OPEN_BOTH_OPEN:
                self.__manager = pywrapcp.RoutingIndexManager(len(self.__distance_matrix),
                                        self.__num_vehicles, self.__startNode)
            elif self.__routeMode == OPEN_FIXED_OPEN:
                self.__manager = pywrapcp.RoutingIndexManager(len(self.__distance_matrix),
                                        self.__num_vehicles, self.__startNode)
            elif self.__routeMode == OPEN_BOTH_FIXED or self.__routeMode == OPEN_OPEN_FIXED:
                self.__manager = pywrapcp.RoutingIndexManager(len(self.__distance_matrix),
                                        self.__num_vehicles, self.__startNode, self.__endNode)
   
            self.__routing = pywrapcp.RoutingModel(self.__manager)
            transit_callback_index = self.__routing.RegisterTransitCallback(self.__distance_callback)
            self.__routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            # guided local search: the default search stops at the first local optimum (Europe, 27 capitals: 18307
            # instead of 16129 km) - it runs until the time limit, 1 s per 20 nodes (at least 1 s, at most 30 s)
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.seconds = max(1, min(30, len(self.__distance_matrix) // 20))
            self.__solution = self.__routing.SolveWithParameters(search_parameters)
        except:
            raise LogLabException('LogisticsLab: Something went wrong while solving TSP: '+ str(sys.exc_info())  )


class OpenTsp(TspMaster):
    """ 
        OpenTsp class 
        Solves open tsp problems
        Arguments:
            distances - distance matrix - 2-D list of int or float
            edges - edges - list or tuple list of tuples (int,int) - default : None
            startNode - starting and end node - int
            endNode - end node - int or None     
        """
    def __init__(self, distances, edges=None, startNode=0, endNode=None):
        TspMaster.__init__(self, distances, edges, startNode, endNode, openRoute=True)

class Tsp(TspMaster):
    """ 
        Tsp class 
        Solves tsp problems
        Arguments:
            distances - distance matrix - 2-D list of int or float
            edges - edges - list or tuple list of tuples (int,int) - default : None
            startNode - starting node - int or None  
    """
    def __init__(self, distances, edges=None, startNode=0):
        TspMaster.__init__(self, distances, edges, startNode, endNode=None, openRoute=False)
from .tools import *
from .exception import *

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import sys
import traceback


#*************** CmplCPP  ************************************************
class Vrp(object):
        
    #*********** constructor **********
    def __init__(self, distMatrix, demands, capacities, depot, timeMatrix, timeWindows, serviceTimes):
            
        self.__time_matrix = setIntMatrix(timeMatrix)

        self.__time_windows = self.__setTimeWindows(timeWindows)
        self.__service_times = setIntVector(serviceTimes)
        self.__distance_matrix = setIntMatrix(distMatrix)

        self.__demands = setIntVector(demands)
        self.__vehicle_capacities = setIntVector(capacities)

        self.__num_vehicles = len( self.__vehicle_capacities )

        self.__depot = depot

        if self.__time_matrix:
            self.__isTimeMatrix = True
            self.__isTimeWindow = True
        else:
            self.__isTimeMatrix = False  
            self.__isTimeWindow = False   

        self.__isMaxTime = False
        self.__isMaxDist = False

        self.__maxTime = 0
        self.__maxDist = 0
        self.__maxWaitingTime = 30

        self.__maxSolvingTime = 3

        if self.__time_matrix:
            self.__isTimeMatrix = True
        else:
            self.__isTimeMatrix = False 

        if self.__maxDist>0:
            self.__isMaxDist = True
        else:
            for dRow in self.__distance_matrix:
                self.__maxDist += max(dRow)
            
        if self.__maxTime>0:
            self.__isMaxTime = True  
        else:
            if self.__isTimeMatrix:
                for tRow in self.__time_matrix:
                    self.__maxTime += max(tRow)

        self.__maxWaitingTime = round(self.__maxTime / len(self.__demands))

        self.__routeIndices = []
        self.__routeLoads = []
        self.__routeTimes = [] 
        self.__routeDistances = []

        self.__solutionStatus = False
        self.__objValue = 0

        self.__manager = None
        self.__routing = None
        self.__solution = None


    #*********** end constructor ******

    
    def __setTimeWindows(self, timeWindows):
        if timeWindows!=None:
            if not isinstance(timeWindows, (list, tuple)):
                raise LogLabException(f'LogisticsLab error: Wrong time windows. It is not an list or tuple.')
        
            for t in timeWindows:
                if not isinstance(t,(list, tuple)) or not all(isinstance(i,int) for i in t):
                    raise LogLabException(f'LogisticsLab error: Wrong time windows {t}')
                
        return timeWindows
         

    def distance_callback(self, from_index, to_index):
        from_node = self.__manager.IndexToNode(from_index)
        to_node = self.__manager.IndexToNode(to_index)
        return self.__distance_matrix[from_node][to_node]

    def time_callback(self, from_index, to_index):
        from_node = self.__manager.IndexToNode(from_index)
        to_node = self.__manager.IndexToNode(to_index)
        return (self.__time_matrix[from_node][to_node] + self.__service_times[from_node] )

    def demand_callback(self, from_index):
        from_node = self.__manager.IndexToNode(from_index)
        return self.__demands[from_node]

    def getSolutionData(self):
        
        self.__objValue = self.__solution.ObjectiveValue()

        if self.__isTimeWindow or self.__isMaxTime:
            time_dimension = self.__routing.GetDimensionOrDie('Time')

        route_distance = 0
        for vehicle_id in range(self.__num_vehicles):
            index = self.__routing.Start(vehicle_id)

            rIndices = []
            rLoads = []
            rTimes = [] 
            rDists = []
            
            route_distance = 0
            if self.__isTimeWindow or self.__isMaxTime:
                time_var = time_dimension.CumulVar(index)
                rTimes.append(self.__solution.Min(time_var))
                rDists.append(0)

            while not self.__routing.IsEnd(index):
                node_index = self.__manager.IndexToNode(index)

                previous_index = index
                index = self.__solution.Value(self.__routing.NextVar(index))

                
                route_distance += self.__routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id)

                if self.__isTimeWindow or self.__isMaxTime:
                    time_var = time_dimension.CumulVar(index)

                rIndices.append(node_index)
                rLoads.append(self.__demands[node_index])
                rDists.append(route_distance)
                
                if self.__isTimeWindow or self.__isMaxTime:
                    rTimes.append(self.__solution.Min(time_var))
                   
            node_index = self.__manager.IndexToNode(index)
            rIndices.append(node_index)
            rLoads.append(self.__demands[node_index])

            self.__routeIndices.append(rIndices)
            self.__routeLoads.append(rLoads)
            self.__routeTimes.append(rTimes)
            self.__routeDistances.append(rDists)
            #print(route_distance)


    def solve(self):
        print('VRP has been started ')
        try:
            self.__manager = pywrapcp.RoutingIndexManager(len(self.__distance_matrix),
                                           self.__num_vehicles, self.__depot)

            self.__routing = pywrapcp.RoutingModel(self.__manager)

            dist_callback_index = self.__routing.RegisterTransitCallback(self.distance_callback)
            self.__routing.SetArcCostEvaluatorOfAllVehicles(dist_callback_index)

            if self.__isMaxDist:
                dist = 'Dist'
                self.__routing.AddDimension( dist_callback_index,  0,  self.__maxDist , 
                                    False, dist)

            if self.__isTimeWindow or self.__isMaxTime:

                if not self.__isTimeMatrix:
                    raise LogLabException('Specify time matrix before using time windows or max time')

                time_callback_index = self.__routing.RegisterTransitCallback(self.time_callback)

                time = 'Time'
                self.__routing.AddDimension( time_callback_index, self.__maxWaitingTime, 
                                                self.__maxTime, False, time)
                                                
                time_dimension = self.__routing.GetDimensionOrDie(time)
               
                if self.__isTimeWindow:
                    # Add time window constraints for each location except depot.
                    for location_idx, time_window in enumerate(self.__time_windows):
                        if location_idx == self.__depot:
                            continue
                        index = self.__manager.NodeToIndex(location_idx)
                        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

                    # Add time window constraints for each vehicle start node.
                    depot_idx = self.__depot
                    for vehicle_id in range(self.__num_vehicles):
                        index = self.__routing.Start(vehicle_id)
                        time_dimension.CumulVar(index).SetRange(
                                        self.__time_windows[depot_idx][0],
                                        self.__time_windows[depot_idx][1])

                    # Instantiate route start and end times to produce feasible times.
                    for i in range(self.__num_vehicles):
                        self.__routing.AddVariableMinimizedByFinalizer(
                                time_dimension.CumulVar(self.__routing.Start(i)))
                        self.__routing.AddVariableMinimizedByFinalizer(
                                time_dimension.CumulVar(self.__routing.End(i)))
          
            demand_callback_index = self.__routing.RegisterUnaryTransitCallback(self.demand_callback)

            self.__routing.AddDimensionWithVehicleCapacity(demand_callback_index,
                                                        0,  self.__vehicle_capacities,  
                                                        True, 'Capacity')
            
            
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
            
            search_parameters.local_search_metaheuristic = (
                       routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)

            #search_parameters.first_solution_strategy = (
            #            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
            #search_parameters.local_search_metaheuristic = (
            #            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
            #search_parameters.time_limit.FromSeconds(1)
           
            search_parameters.time_limit.seconds = self.__maxSolvingTime

      
            self.__solution = self.__routing.SolveWithParameters(search_parameters)

            if self.__solution:
                self.__solutionStatus = True
                self.getSolutionData()
                print(' ... solution has been found ')
                print(' ... Writing results ')
               
            else:
                self.__solutionStatus = False
                print(' ... no solution has been found ')
   
            print('VRP has been finished ')
      
            #self.lf.close()
        except:
            traceback.print_exc()
            print('Error :'+str(sys.exc_info()) )
            #self.lf.close()
            raise LogLabException('LogisticsLab: Something went wrong while solving VRP: '+ str(sys.exc_info()) )
    
    def setMaxWaitingTime(self, maxWaitingTime):
        self.__maxWaitingTime = maxWaitingTime

    def setMaxTime(self, maxTime):
        self.__maxTime = maxTime    
        self.__isMaxTime = True    

    def setMaxDist(self, maxDist):
        self.__maxDist = maxDist    
        self.__isMaxDist = True     

    def setMaxSolvingTime(self, maxTime):
        self.__maxSolvingTime = maxTime

    def useTimeWindows(self, tw = True):
        self.__isTimeWindow = tw
    
    
    def isSolution(self):
        return self.__solutionStatus

    def getObjValue(self):
        return self.__objValue

    def getRouteIndices(self):
        return self.__routeIndices

    def getRouteLoads(self):
        return self.__routeLoads

    def getRouteTimes(self):
        if self.__isTimeWindow:
            return self.__routeTimes
        else:
            return None

    def getRouteDistances(self):
        return self.__routeDistances
    



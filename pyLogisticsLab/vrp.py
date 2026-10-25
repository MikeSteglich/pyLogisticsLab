from .tools import *
from .exception import *

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import sys
import traceback
import logging

logger = logging.getLogger(__name__)


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
        self.__maxWaitingTimeSet = None   # maximal waiting before a time window - None: the horizon
        self.__fixedStart = False     # True: every route starts at the start of the time window of the depot
        self.__vehicleFixedCost = 0   # > 0: costs of every used vehicle - the number of routes is minimised first
        self.__pickupsDeliveries = [] # pickup and delivery: pairs of nodes (pickup, delivery) on the same route
        self.__handlingTimes = None   # service time per node beside the stop time - e.g. per unit of the demand
        self.__locations = None       # place of every node - nodes at the same place one after another: one stop time

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

    def serviceTime(self, from_node, to_node):
        """ service at from_node before going to to_node: its handling time and its stop time - the stop time only
            once for nodes at the same place one after another (paid when the vehicle leaves the place) """
        s = self.__handlingTimes[from_node] if self.__handlingTimes else 0
        if not (self.__locations and self.__locations[from_node] == self.__locations[to_node]):
            s += self.__service_times[from_node]
        return s

    def time_callback(self, from_index, to_index):
        from_node = self.__manager.IndexToNode(from_index)
        to_node = self.__manager.IndexToNode(to_index)
        return self.__time_matrix[from_node][to_node] + self.serviceTime(from_node, to_node)

    def demand_callback(self, from_index):
        from_node = self.__manager.IndexToNode(from_index)
        return self.__demands[from_node]

    def getSolutionData(self):
        
        # the objective without the fixed costs of the vehicles: the distance
        used = sum(1 for v in range(self.__num_vehicles) if self.__routing.IsVehicleUsed(self.__solution, v))
        self.__objValue = self.__solution.ObjectiveValue() - self.__vehicleFixedCost * used

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
            rDists.append(0)            # distance at the start - one value per node of the route, also without times
            if self.__isTimeWindow or self.__isMaxTime:
                time_var = time_dimension.CumulVar(index)
                rTimes.append(self.__solution.Min(time_var))

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
        logger.info('VRP has been started ')
        try:
            self.__manager = pywrapcp.RoutingIndexManager(len(self.__distance_matrix),
                                           self.__num_vehicles, self.__depot)

            self.__routing = pywrapcp.RoutingModel(self.__manager)

            dist_callback_index = self.__routing.RegisterTransitCallback(self.distance_callback)
            self.__routing.SetArcCostEvaluatorOfAllVehicles(dist_callback_index)
            if self.__vehicleFixedCost > 0:
                self.__routing.SetFixedCostOfAllVehicles(self.__vehicleFixedCost)

            if self.__isMaxDist:
                dist = 'Dist'
                self.__routing.AddDimension( dist_callback_index,  0,  self.__maxDist , 
                                    False, dist)

            if self.__isTimeWindow or self.__isMaxTime:

                if not self.__isTimeMatrix:
                    raise LogLabException('Specify time matrix before using time windows or max time')

                time_callback_index = self.__routing.RegisterTransitCallback(self.time_callback)

                # the times are clock times (time windows from the start of the day) - the horizon covers the
                # latest time window and the longest possible route after it
                horizon = sum(max(row) for row in self.__time_matrix) + sum(self.__service_times) + \
                          sum(self.__handlingTimes or [])
                if self.__isTimeWindow:
                    finite = [ t for tw in self.__time_windows for t in tw if t < 10**8 ]
                    horizon += max(finite + [0])
                # waiting before a time window may be long (start at 7, window from 10)
                slack = self.__maxWaitingTimeSet if self.__maxWaitingTimeSet is not None else horizon
                time = 'Time'
                self.__routing.AddDimension(time_callback_index, slack, horizon, False, time)
                time_dimension = self.__routing.GetDimensionOrDie(time)

                # maximal duration of a route: from its start to its end
                if self.__isMaxTime:
                    for vehicle_id in range(self.__num_vehicles):
                        time_dimension.SetSpanUpperBoundForVehicle(self.__maxTime, vehicle_id)

                if self.__isTimeWindow:
                    # time windows of the customers
                    for location_idx, time_window in enumerate(self.__time_windows):
                        if location_idx == self.__depot:
                            continue
                        index = self.__manager.NodeToIndex(location_idx)
                        time_dimension.CumulVar(index).SetRange(time_window[0], min(time_window[1], horizon))

                    # time window of the depot: the start of the routes and their latest return - with a fixed start
                    # every route starts at the beginning of the window (waiting at the customers if needed)
                    depot_tw = self.__time_windows[self.__depot]
                    for vehicle_id in range(self.__num_vehicles):
                        start, end = self.__routing.Start(vehicle_id), self.__routing.End(vehicle_id)
                        if self.__fixedStart:
                            time_dimension.CumulVar(start).SetRange(depot_tw[0], depot_tw[0])
                        else:
                            time_dimension.CumulVar(start).SetRange(depot_tw[0], min(depot_tw[1], horizon))
                        time_dimension.CumulVar(end).SetRange(depot_tw[0], min(depot_tw[1], horizon))

                    # first the routes end as early as possible, then they start as late as possible - no waiting at
                    # the depot (the finalizer fixes the variables in this order)
                    for i in range(self.__num_vehicles):
                        self.__routing.AddVariableMinimizedByFinalizer(
                                time_dimension.CumulVar(self.__routing.End(i)))
                    for i in range(self.__num_vehicles if not self.__fixedStart else 0):
                        self.__routing.AddVariableMaximizedByFinalizer(
                                time_dimension.CumulVar(self.__routing.Start(i)))

            demand_callback_index = self.__routing.RegisterUnaryTransitCallback(self.demand_callback)

            self.__routing.AddDimensionWithVehicleCapacity(demand_callback_index,
                                                        0,  self.__vehicle_capacities,  
                                                        True, 'Capacity')

            # pickup and delivery: the demand of a pickup is positive, of its delivery negative - the load of the
            # vehicle stays between 0 and its capacity; both on the same route, the pickup first
            if self.__pickupsDeliveries:
                if not self.__isMaxDist:
                    self.__routing.AddDimension(dist_callback_index, 0, self.__maxDist, True, 'Dist')
                dist_dimension = self.__routing.GetDimensionOrDie('Dist')
                solver = self.__routing.solver()
                for pickup, delivery in self.__pickupsDeliveries:
                    p = self.__manager.NodeToIndex(pickup)
                    d = self.__manager.NodeToIndex(delivery)
                    self.__routing.AddPickupAndDelivery(p, d)
                    solver.Add(self.__routing.VehicleVar(p) == self.__routing.VehicleVar(d))
                    solver.Add(dist_dimension.CumulVar(p) <= dist_dimension.CumulVar(d))

            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
                        if self.__pickupsDeliveries else routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
            
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
                logger.info(' ... solution has been found ')
                logger.info(' ... Writing results ')
               
            else:
                self.__solutionStatus = False
                logger.info(' ... no solution has been found ')
   
            logger.info('VRP has been finished ')
      
            #self.lf.close()
        except:
            traceback.print_exc()
            logger.info('Error :'+str(sys.exc_info()))
            #self.lf.close()
            raise LogLabException('LogisticsLab: Something went wrong while solving VRP: '+ str(sys.exc_info()) )
    
    def setMaxWaitingTime(self, maxWaitingTime):
        self.__maxWaitingTime = maxWaitingTime
        self.__maxWaitingTimeSet = maxWaitingTime

    def setMaxTime(self, maxTime):
        self.__maxTime = maxTime    
        self.__isMaxTime = True    

    def setMaxDist(self, maxDist):
        self.__maxDist = maxDist    
        self.__isMaxDist = True     

    def setMaxSolvingTime(self, maxTime):
        self.__maxSolvingTime = maxTime

    def setFixedStart(self, fixed=True):
        """ every route starts at the start of the time window of the depot - otherwise as late as possible """
        self.__fixedStart = fixed

    def setVehicleFixedCost(self, cost):
        """ costs of every used vehicle - larger than any distance saved: as few routes as possible, then the
            shortest total distance """
        self.__vehicleFixedCost = int(cost)

    def setPickupsDeliveries(self, pairs):
        """ pickup and delivery: pairs of node indices (pickup, delivery) - served by the same vehicle, the pickup
            before the delivery; the demand of the pickup is positive, the demand of the delivery negative """
        n = len(self.__distance_matrix)
        for pair in pairs:
            if len(pair) != 2 or not all(isinstance(i, int) and 0 <= i < n and i != self.__depot for i in pair):
                raise LogLabException(f'LogisticsLab error: Wrong pickup and delivery {pair}')
        used = [ i for pair in pairs for i in pair ]
        if len(used) != len(set(used)):
            raise LogLabException('LogisticsLab error: a node in more than one pickup and delivery')
        self.__pickupsDeliveries = [ tuple(pair) for pair in pairs ]

    def setHandlingTimes(self, times):
        """ service time of every node beside its stop time (serviceTimes) - e.g. the time per unit times the demand """
        self.__handlingTimes = setIntVector(times)

    def setLocations(self, locations):
        """ place of every node - nodes at the same place visited one after another need the stop time only once """
        self.__locations = list(locations)

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
        if self.__isTimeWindow or self.__isMaxTime:
            return self.__routeTimes
        else:
            return None

    def getRouteDistances(self):
        return self.__routeDistances
    



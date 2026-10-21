""" handlers of the routing problems on graphs and with vehicles: cpp, vrp """

import pyLogisticsLab as ll
from pyCmpl import CmplException
from .exception import *
from .problemHandler import *
import sys


def toInt(value):
    """ OR-Tools needs integers - numbers are rounded, lists are converted recursively """
    if isinstance(value, list):
        return [ toInt(v) for v in value ]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(value))
    return value


class CppHandler(ProblemHandler):
    """ chinese postman problem - euler tour over all edges, edges are used several times if necessary """

    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)
        self._logger.debug('cpp', 'init cpp')

        d = problemData
        if not d.edges:
            raise LogLabCoreException('no edges are available')
        weights = self._checkLength(d.edgeWeights, len(d.edges), 'edgeWeights')
        types = self._checkLength(d.edgeTypes, len(d.edges), 'edgeTypes', default=1)

        nodes = { n for e in d.edges if isinstance(e, (list, tuple)) for n in e }
        if d.startNode not in nodes:
            raise LogLabCoreException(f'start node {d.startNode} is not a node of the edges')
        self._checkNrOfNodes(len(nodes))
        self._size = f'{len(nodes)} nodes, {len(d.edges)} edges'

        try:
            self.__problem = ll.Cpp(d.edges, types, weights, d.startNode,
                                    mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime))
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

    def solve(self):
        try:
            self._logger.debug('cpp', 'solve')
            self.__problem.solve()
        except ll.LogLabException as e:
            raise LogLabCoreException(e)
        except CmplException as e:
            # CMPL reports infeasible models of HiGHS as error
            self._logger.info('cpp', f'no solution - {e}')
            self._isSolution = False
            return
        except Exception:
            raise LogLabCoreException(str(sys.exc_info()))

        self._isSolution = self.__problem.isEulerTour()
        if self._isSolution:
            self._objVal = self.__problem.getObjValue()
            self._results['eulerTour'] = self.__problem.getEulerTour()
            self._results['edgeUsages'] = self.__problem.getEdgeUsages()


class VrpHandler(ProblemHandler):
    """ capacitated vehicle routing problem, optionally with time windows, maximal route duration and distance """

    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)
        self._logger.debug('vrp', 'init vrp')

        d = problemData
        usesTimes = d.timeWindows is not None or d.maxTime is not None
        self.__calculated = {}          # matrices loaded via OSM - sent back with the results

        if d.distances:
            distances = d.distances
            times = d.times
        elif d.coordinates:
            self._logger.debug('vrp', 'load distances')
            distances = self._loadMatrix(d.coordinates, d, 'distances')
            times = self._loadMatrix(d.coordinates, d, 'times') if usesTimes else d.times
            self.__calculated = {'distances': distances, **({'times': times} if usesTimes else {})}
        else:
            raise LogLabCoreException('no distances and coordinates are available')

        if usesTimes and not times:
            raise LogLabCoreException('times are needed for timeWindows and maxTime')

        n = len(distances)
        self._checkNrOfNodes(n)
        if not (0 <= d.depot < n):
            raise LogLabCoreException(f'wrong depot {d.depot} - between 0 and {n-1} expected')
        if not d.capacities:
            raise LogLabCoreException('no vehicles - capacities are missing')
        self._size = f'{n} nodes, {len(d.capacities)} vehicles'

        demands = self._checkLength(d.demands, n, 'demands')
        timeWindows = self._checkLength(d.timeWindows, n, 'timeWindows') if d.timeWindows is not None else None
        serviceTimes = self._checkLength(d.serviceTimes, n, 'serviceTimes', default=0) if times else []

        try:
            self.__problem = ll.Vrp(toInt(distances), toInt(demands), toInt(d.capacities), d.depot,
                                    toInt(times) if times else [], toInt(timeWindows), toInt(serviceTimes))
            # time windows only if they are given - the library assumes them for every time matrix
            self.__problem.useTimeWindows(timeWindows is not None)
            if d.maxTime is not None:
                self.__problem.setMaxTime(int(d.maxTime))
            if d.maxDist is not None:
                self.__problem.setMaxDist(int(d.maxDist))
            if d.maxWaitingTime is not None:
                self.__problem.setMaxWaitingTime(int(d.maxWaitingTime))
            self.__problem.setMaxSolvingTime(int(self._maxSolvingTime(d.maxSolvingTime)))
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

        # route times with time windows or a maximal route duration - otherwise there are no times
        self.__routeTimes = timeWindows is not None or d.maxTime is not None

    def solve(self):
        try:
            self._logger.debug('vrp', 'solve')
            self.__problem.solve()
        except ll.LogLabException as e:
            raise LogLabCoreException(e)
        except Exception:
            raise LogLabCoreException(str(sys.exc_info()))

        self._isSolution = self.__problem.isSolution()
        if self._isSolution:
            p = self.__problem
            self._objVal = p.getObjValue()
            self._results['routes'] = p.getRouteIndices()
            self._results['routeLoads'] = p.getRouteLoads()
            self._results['routeDistances'] = p.getRouteDistances()
            if self.__routeTimes:
                self._results['routeTimes'] = p.getRouteTimes()
            self._results.update(self.__calculated)

import pyLogisticsLab as ll
from .exception import *
from .problemHandler import *
import sys


class TspHandler(ProblemHandler):
    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)

        self._logger.debug('tsp','init tsp')
        edges = problemData.edges

        startNode=problemData.startNode
        endNode=problemData.endNode
        openRoute=problemData.openRoute

        if startNode!=endNode:
            openRoute=True

        if not problemData.distances:
            if not problemData.coordinates:
                raise LogLabCoreException('no distances and coordinates are available')
            self._logger.debug('tsp','load distances')
            self.__distances=self._loadMatrix(problemData.coordinates, problemData, problemData.matrixMode)
        else:
            self.__distances=problemData.distances

        self._checkNrOfNodes(len(self.__distances))
        self._size=f'{len(self.__distances)} nodes'

        try:
            self.__problem=ll.TspMaster(self.__distances, edges=edges, startNode=startNode, endNode=endNode, openRoute=openRoute)
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

        self._logger.debug('tsp','init done')

    def solve(self):
        try:
            self._logger.debug('tsp','solve')
            self.__problem.solve()
            self._isSolution = self.__problem.isSolution()
            if self._isSolution:
                self._objVal, route = self.__problem.solution()
                self._results['route'] = route
        except ll.LogLabException as e:
            raise LogLabCoreException(e)
        except:
            raise LogLabCoreException(str(sys.exc_info()))

import osm_data as osm
from exception import *


class ProblemHandler:
    """ base class of all problem handlers

        A handler is created with (problemData, logger, conf) and has to implement solve().
        After solve() it provides
            isSolution  - True if a solution has been found
            objVal      - objective function value
            results     - dict with the problem specific results
        and the problem size as short string for logging (size).
    """

    def __init__(self, problemData, logger, conf):
        self._logger=logger
        self._conf=conf
        self._isSolution=False
        self._objVal=None
        self._results={}
        self._size=''

    def solve(self):
        raise NotImplementedError

    def _checkNrOfNodes(self, nrOfNodes):
        if self._conf.get('maxNodes'):
            if nrOfNodes>self._conf['maxNodes']:
                raise LogLabServerException(f"number of nodes {nrOfNodes} size exceeds maximum of {self._conf['maxNodes']}")

    def _maxSolvingTime(self, maxSolvingTime):
        if self._conf.get('maxSolvingTime') and maxSolvingTime>self._conf['maxSolvingTime']:
            return self._conf['maxSolvingTime']
        return maxSolvingTime

    def _loadMatrix(self, coordinates, travelmode, matrixMode, sources=None, destinations=None):
        """ loads a rounded distance or time matrix via OSM """
        if not coordinates:
            raise LogLabServerException('no coordinates are available')

        try:
            osmData = osm.Matrix(coordinates, sources=sources, destinations=destinations)

            status, msg= osmData.loadMatrix(travelmode=travelmode)

            if status!=200:
                raise LogLabServerException(msg)

            if matrixMode=="times":
                matrix = osmData.timeMatrix
            else:
                matrix = osmData.distanceMatrix

        except osm.OsmException as e:
            raise LogLabServerException(e)

        return [[round(value) for value in row] for row in matrix]

    def getIsSolution(self):
        return self._isSolution
    isSolution = property(getIsSolution)

    def getObjVal(self):
        return self._objVal
    objVal = property(getObjVal)

    def getSize(self):
        return self._size
    size = property(getSize)

    def getResults(self):
        return self._results
    results = property(getResults)

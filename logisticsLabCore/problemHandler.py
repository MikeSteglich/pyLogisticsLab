import osm_data as osm
from .exception import *


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
                raise LogLabCoreException(f"number of nodes {nrOfNodes} size exceeds maximum of {self._conf['maxNodes']}")

    def _maxSolvingTime(self, maxSolvingTime):
        if self._conf.get('maxSolvingTime') and maxSolvingTime>self._conf['maxSolvingTime']:
            return self._conf['maxSolvingTime']
        return maxSolvingTime

    def _loadMatrix(self, coordinates, travelmode, matrixMode, sources=None, destinations=None):
        """ loads a rounded distance or time matrix via OSM """
        if not coordinates:
            raise LogLabCoreException('no coordinates are available')

        try:
            osmData = osm.Matrix(coordinates, sources=sources, destinations=destinations)

            status, msg= osmData.loadMatrix(travelmode=travelmode)

            if status!=200:
                raise LogLabCoreException(msg)

            if matrixMode=="times":
                matrix = osmData.timeMatrix
            else:
                matrix = osmData.distanceMatrix

        except osm.OsmException as e:
            raise LogLabCoreException(e)

        return [[round(value) for value in row] for row in matrix]

    def _bipartiteMatrix(self, problemData, field):
        """ matrix [sources x destinations] from problemData.<field> or from sourceCoordinates and destinationCoordinates

            returns (matrix, isCalculated)
        """
        matrix = getattr(problemData, field)
        if matrix:
            if not isinstance(matrix, list) or not all(isinstance(row, list) and row for row in matrix):
                raise LogLabCoreException(f'{field} must be a matrix [sources x destinations]')
            return matrix, False

        if not problemData.sourceCoordinates or not problemData.destinationCoordinates:
            raise LogLabCoreException(f'neither {field} nor sourceCoordinates and destinationCoordinates are available')

        self._logger.debug(problemData.type, 'load distances')
        coordinates = problemData.sourceCoordinates + problemData.destinationCoordinates
        nrOfSources = len(problemData.sourceCoordinates)
        matrix = self._loadMatrix(coordinates, problemData.travelmode, problemData.matrixMode,
                                  sources=list(range(nrOfSources)),
                                  destinations=list(range(nrOfSources, len(coordinates))))
        return matrix, True

    def _checkLength(self, vector, length, name, default=None):
        """ checks the length of an optional vector - returns default (a vector of the given length) if it is None """
        if vector is None:
            if default is None:
                raise LogLabCoreException(f'{name} is missing')
            return [default] * length
        if not isinstance(vector, list) or len(vector) != length:
            raise LogLabCoreException(f'wrong length of {name} - {length} values expected')
        return vector

    @staticmethod
    def _zeroBased(index):
        """ 1-based source number of the library -> 0-based index, -1 if no source """
        return index - 1 if isinstance(index, int) and index > 0 else -1

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

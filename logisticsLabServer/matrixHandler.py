import osm_data as osm
from exception import *
import sys


class MatrixHandler:
    def __init__(self, problemData, logger):
        self.__logger=logger

        self.__logger.debug('matrix','init')
        self.__coordinates=problemData.coordinates
        self.__rounded=problemData.rounded
      
        self.__travelmode=problemData.travelmode
        self.__matrixMode=problemData.matrixMode
        self.__sources=problemData.sources
        self.__destinations=problemData.destinations

        self.__distances=None
        self.__durations=None
        self.__httpStatus=200
        self.__message='ok'
        self.__status='ok'

        self.__logger.debug('matrix','done')
        self.__getMatrix()


    def __getMatrix(self):
        if not self.__coordinates:
            raise LogLabServerException('no coordinates available')
            
        try:
            osmData = osm.Matrix(self.__coordinates, sources=self.__sources, destinations=self.__destinations)

            status, msg= osmData.loadMatrix(travelmode=self.__travelmode)

            self.__httpStatus=status
            self.__message=msg

            if status==200:
                
                if self.__matrixMode=='durations':
                    self.__distances = None
                    self.__durations = osmData.timeMatrix
                    self.__message='duration matrix received'
                elif self.__matrixMode=="distances":
                    self.__distances = osmData.distanceMatrix
                    self.__durations = None
                    self.__message='distance matrix received'
                else:
                    self.__durations = osmData.timeMatrix
                    self.__distances = osmData.distanceMatrix
                    self.__message='time and distance matrix received'

                if self.__rounded:
                    if self.__durations:
                        self.__durations = [[round(value) for value in row] for row in self.__durations]
                    if self.__distances:
                        self.__distances = [[round(value) for value in row] for row in self.__distances]
                
        except osm.OsmException as e: 
            self.__status='error'
            self.__message=str(e)
            self.__logger.error('matrix',str(e))
            self.__httpStatus=e.status_code
        else:
            if status!=200:
                self.__status='error'

    
    def getDistances(self):
        return self.__distances
    distances = property(getDistances)

    def getDurations(self):
        return self.__durations
    durations = property(getDurations)

    def getStatus(self):
        return self.__status
    status = property(getStatus)

    def getHttpStatus(self):
        return self.__httpStatus
    httpStatus = property(getHttpStatus)

    def getMessage(self):
        return self.__message
    message = property(getMessage)

    
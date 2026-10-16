import osm_data as osm
from .exception import *
import sys


class RouteHandler:
    def __init__(self, problemData, logger):

        self.__logger=logger

        self.__logger.debug('route','init')
        self.__coordinates=problemData.coordinates
       
        self.__travelmode=problemData.travelmode
        self.__details=problemData.details
        

        self.__route=None
        self.__httpStatus=200
        self.__message='ok'
        self.__status='ok'

        self.__logger.debug('route','done')
        self.__getRoute()


    def __getRoute(self):

        if not self.__coordinates:
            raise LogLabCoreException('no coordinates available')
            
        try:
            osmData = osm.Routing(self.__coordinates)
            status, msg= osmData.loadRoute(travelmode=self.__travelmode, details=self.__details)
            self.__httpStatus=status
            self.__message=msg
      
            if status==200:
                self.__route = osmData.route
                self.__message='route received'
                                
        except osm.OsmException as e: 
            self.__status='error'
            self.__message=str(e)
            self.__logger.error('route',str(e))
            self.__httpStatus=e.status_code
        else:
            if status!=200:
                self.__status='error'

    
    def getRoute(self):
        return self.__route
    route = property(getRoute)

    def getStatus(self):
        return self.__status
    status = property(getStatus)

    def getHttpStatus(self):
        return self.__httpStatus
    httpStatus = property(getHttpStatus)

    def getMessage(self):
        return self.__message
    message = property(getMessage)

    
import osm_data as osm
from .exception import *
import sys


class GeoCodingHandler:
    def __init__(self, problemData, logger, modus='search'):

        if modus not in ['search', 'coordinates', 'reverse']:
            self.__modus='search'
        else:
            self.__modus=modus

        self.__logger=logger

        self.__logger.debug('geo','init')
        self.__data=problemData
        self.__results=None
        self.__hits=None
        self.__httpStatus=200
        self.__message='ok'
        self.__status='ok'

        try:
            self.__osmData = osm.Geocoding()
        except osm.OsmException as e: 
            self.__status='error'
            self.__message=str(e)
            self.__logger.error('geo',str(e))

        self.__logger.debug('geo','done')
        self.__getData()
      

    def __getData(self):

        if self.__modus=='coordinates' and not self.__data.adresses:
            raise LogLabCoreException('no adresses available')
        
        if self.__modus=='search' and not self.__data.adress:
            raise LogLabCoreException('no adress available')
            
        try:
            self.__message='ok'
            self.__status='ok'
            if self.__modus=='coordinates':
                status, msg= self.__osmData.loadCoordinates(self.__data.adresses, limit=self.__data.limit or 1,
                                                            countrycodes=self.__data.countrycodes, near=self.__data.near)
            elif self.__modus=='search':
                status, msg= self.__osmData.search(self.__data.adress)
            elif self.__modus=='reverse':
                status, msg= self.__osmData.reverse(self.__data.coordinate)

            self.__httpStatus=status
            self.__message=msg

            if status==200:
                if self.__modus=='coordinates':
                    self.__results= self.__osmData.coordinates
                    self.__hits= self.__osmData.hits
                elif self.__modus=='search' or self.__modus=='reverse':
                    self.__results= self.__osmData.results
            
                self.__message='geoData received'

        except osm.OsmException as e: 
            self.__status='error'
            self.__message=str(e)
            self.__logger.error('coordinates',str(e))
            self.__httpStatus=e.status_code
        else:
            if status!=200:
                self.__status='error'

    def getResults(self):
        return self.__results
    results = property(getResults)

    def getHits(self):
        return self.__hits
    hits = property(getHits)
  
    def getStatus(self):
        return self.__status
    status = property(getStatus)

    def getHttpStatus(self):
        return self.__httpStatus
    httpStatus = property(getHttpStatus)

    def getMessage(self):
        return self.__message
    message = property(getMessage)

    
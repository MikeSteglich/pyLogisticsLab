#***********************************************************************
 #  This code is part of pyLogisticsLab
 #
 #  Mike Steglich - Technical University of Applied Sciences
 #  Wildau, Germany
 #
 #  pyLogisticsLab is a project of the Technical University of
 #  Applied Sciences Wildau
 #
 #  pyLogisticsLab is free software; you can redistribute it and/or modify it
 #  under the terms of the GNU Lesser General Public License as published by
 #  the Free Software Foundation; either version 3 of the License, or
 #  (at your option) any later version.
 #
 #  pyLogisticsLab is distributed in the hope that it will be useful, but WITHOUT
 #  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 #  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
 #  License for more details.
 #
 #  You should have received a copy of the GNU Lesser General Public License
 #  along with this program; if not, see <http://www.gnu.org/licenses/>.
 #
 #**********************************************************************

from .exception import *
from .config import *
from .logging import *
from .scheduler import *
from .tools import *

import sys


class Geocoding:
    def __init__(self, conf=None):

        if conf:
            checkConfig(conf)
            self.__config = conf
        else:
            self.__config = readConf()

        self.__log = Logging(self.__config.get('logFile'),self.__config['logging'])
        self.__osmScheduler = Scheduler(self.__config, self.__log) 

        self.__addresses=[]
        self.__coordinates=[]

        self.__results=[]


    def getaddress(self):
        return self.__getaddressList[0]
    address = property(getaddress)

    def getaddressList(self):
        self.__addresses=[]
        for r in self.__results:
            tmpaddr=[]
            tmpaddr.append(r['coordinates'][0])
            tmpaddr.append(r['coordinates'][1])
            tmpaddr.append(r['name'])
            tmpaddr.append(r['city'])
            tmpaddr.append(r['postcode'])
            tmpaddr.append(r['street'])
            tmpaddr.append(r['country'])
            tmpaddr.append(r['countrycode'])

            self.__addresses.append(tmpaddr)
        return self.__addresses
    addresses = property(getaddressList)

    def getCoordinates(self):
        return self.__coordinates
    coordinates = property(getCoordinates)
        
    def getResults(self):
        return self.__results
    results = property(getResults)




    def loadCoordinates(self,addresses ):
        
        msg='OK'
        self.__coordinates=[]
        adrList=checkStrList(addresses)
        
        try:
            self.__log.logging('getCoordinates',f'number of requests:  {len(adrList)}','start')
            for adr in adrList:
                
                params = {'q' : adr }
                           
                serverTyp, status, data = self.__osmScheduler.openUrl(params=params, mode='geoCoords')
                
                if status!=200:
                    msg='Failed'
                    if serverTyp=='photon':
                        msg=f"Something went wrong while getting OSM routes : {status, data['message'] } "
                    elif serverTyp=='nominatim':
                        msg=f"Something went wrong while getting OSM routes : {data['error']['code'], data['error']['message'] } "
                    raise OsmException(msg, status_code=status) 
                else:
                    if serverTyp=='photon':
                        if data:
                            if data['features']:
                                coords = data['features'][0]['geometry']['coordinates']
                            else: 
                                coords=(0,0)
                        else:
                            coords=(0,0)
                    elif serverTyp=='nominatim':
                        if data:
                            lat = data[0]['lat']
                            lon = data[0]['lon']
                            coords =(lat,lon)  
                        else:
                            coords=(0,0)
                
                    self.__coordinates.append((coords[1],coords[0]))

            self.__log.logging('getCoordinates',f'number of requests:  {len(adrList)}','done')  

            return status,msg

        except OsmException as e:
            raise OsmException(str(e),status_code=e.status_code)
        except:
            raise OsmException(f'Something went wrong while getting OSM coordinates: {str(sys.exc_info()[0])}')
   
    def __setResultDefault(self):
        result={}
        result['coordinates'] = (0,0)
        result['name'] = ''
        result['city']=''
        result['postcode']=''
        result['street']=''
        result['addresstype']=''
        result['country']=''
        result['countrycode'] = ''
        return result
    

    def __parseResults(self,serverTyp, data):
        if serverTyp=='photon':
            if data:
                if not data['features']:
                    self.__results.append(self.__setResultDefault())
                else:
                    for e in data['features']:
                        result=self.__setResultDefault()
                        coords = e['geometry']['coordinates']
                        result['coordinates'] = ( coords[1],coords[0])
           
                        if 'name' in e['properties']: 
                            result['name'] = e['properties']['name']
                        else:
                            result['name'] = ''

                        if 'city' in e['properties']: 
                            result['city']=e['properties']['city']
                        else:
                            result['city']=''

                        if 'postcode' in e['properties']: 
                            result['postcode']=e['properties']['postcode']
                        else:
                            result['postcode']=''

                        if 'street' in e['properties']:
                            if 'housenumber' in e['properties']:
                                result['street'] = e['properties']['street'] +' ' +e['properties']['housenumber']
                            else:
                                result['street'] = e['properties']['street']
                        else:
                            result['street']=''

                        if 'osm_key' in e['properties']:
                            result['addresstype']= e['properties']['osm_key']
                        else:
                            result['addresstype']=''

                        result['country']=e['properties']['country']
                        result['countrycode'] = e['properties']['countrycode']

                        self.__results.append(result)
            else:
                self.__results.append(self.__setResultDefault())

        elif serverTyp=='nominatim':
            if data:

                if 'error' in data:
                    self.__results.append(self.__setResultDefault())
                else:
                    if isinstance(data,dict):
                        data=[data]
                    for e in data:
                   
                        result=self.__setResultDefault()

                        lat = e['lat']
                        lon = e['lon']
                        result['coordinates'] = (lat,lon)  
                        
                        result['name'] = e['name']

                        if 'village' in e['address']:
                            result['city']=e['address']['village']+','
                        else:
                            result['city']=''
                        if 'city' in  e['address']:
                            result['city']+=e['address']['city']

                        if 'postcode' in e['address']:
                            result['postcode']=e['address']['postcode']
                        else:
                            result['postcode']=''
                            
                        if 'road' in e['address']:
                            if 'housenumber' in e['address']:
                                result['street'] = e['address']['road'] +' ' +e['address']['housenumber']
                            else:
                                result['street'] = e['address']['road']
                        else: 
                            result['street'] = ''

                        result['country']=e['address']['country']
                        result['countrycode'] = e['address']['country_code']

                        result['addresstype'] = e['addresstype']

                        self.__results.append(result)
            else:
                self.__results.append(self.__setResultDefault())

    def search(self, address):
        
        msg='OK'
        self.__results=[]
    
        if not isinstance(address, str):
            raise OsmException(f'Something went wrong while getting OSM coordinates: no address given')
       
        try:
            self.__log.logging('search',f' for address:  {address}','start')
            
            params = {'q' : address }
                           
            serverTyp, status, data = self.__osmScheduler.openUrl(params=params, mode='geoSearch')
                
            if status!=200:
                msg='Failed'
                if serverTyp=='photon':
                    msg=f"Something went wrong while searching OSM data : {status, data['message'] } "
                elif serverTyp=='nominatim':
                    msg=f"Something went wrong while searching OSM data : {data['error']['code'], data['error']['message'] } "
                raise OsmException(msg) 
            else:
               self.__parseResults(serverTyp,data)
                                          
            self.__log.logging('search',f' for address:  {address}','done')

            return status,msg

        except OsmException as e:
            raise OsmException(str(e))
        except:
            raise OsmException(f'Something went wrong while searching OSM data: {str(sys.exc_info()[0])}')


    def reverse(self, coordinates):

        checkSingleCoordinates(coordinates)
        
        msg='OK'
        self.__results=[]
          
        try:
            self.__log.logging('reverse',f' for coordinates:  {coordinates}','start')
            
            params = {  'lat' : coordinates[0],
                        'lon' : coordinates[1]
                     }
                           
            serverTyp, status, data = self.__osmScheduler.openUrl(params=params, mode='geoReverse')
                
            if status!=200:
                msg='Failed'
                if serverTyp=='photon':
                    msg=f"Something went wrong while reverse searching OSM data : {status, data['message'] } "
                elif serverTyp=='nominatim':
                    msg=f"Something went wrong while reverse searching OSM data : {data['error']['code'], data['error']['message'] } "
                raise OsmException(msg) 
            else:
               self.__parseResults(serverTyp,data)
                                          
            self.__log.logging('reverse',f' for coordinates:  {coordinates}','done')

            return status,msg

        except OsmException as e:
            raise OsmException(str(e))
        except:
            raise OsmException(f'Something went wrong while reverse searching OSM data: {str(sys.exc_info()[0])}')

  
   
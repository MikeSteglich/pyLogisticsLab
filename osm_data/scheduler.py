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
from .tools import *
from .logging import *
import requests
import sys
import random


class Scheduler:
    def __init__(self, config, log):

        checkConfig(config)
        self.__conf=config
        checkLog(log)
        self.__log=log
        
       
    def __del__(self):
        pass

    
    def __openUrl(self, url, payload=None, params=None, api_key=None, timeOutConnect=3 , timeOutRead=120):
        headers = {
            'Referer' : 'http://logisticsLab.org',
            'User-Agent': 'LogisticsLab',
            'Content-Type': 'application/json',
            'charset' : 'utf-8',
            'Accept-Language': 'en-GB, en-US'
        }
        
        if api_key:
            #headers['api_key']=api_key 
            headers['Authorization']=api_key 

        try:
            if not payload and not params:  
                if not 'proxies' in self.__conf:
                    response=requests.get(url, headers=headers, timeout=(timeOutConnect,timeOutRead) )
                else:
                    response=requests.get(url, headers=headers, proxies=self.__conf['proxies'], timeout=(timeOutConnect,timeOutRead))
            elif not payload and params: 
                if not 'proxies' in self.__conf:
                    response=requests.get(url, params=params, headers=headers, timeout=(timeOutConnect,timeOutRead) )
                else:
                    response=requests.get(url, params=params, headers=headers, proxies=self.__conf['proxies'], timeout=(timeOutConnect,timeOutRead))
            elif payload:
                if not 'proxies' in self.__conf:
                    response=requests.post(url, json=payload, headers=headers, timeout=(timeOutConnect,timeOutRead))
                else:
                    response=requests.post(url, json=payload, headers=headers, proxies=self.__conf['proxies'], timeout=(timeOutConnect,timeOutRead))
        except:
            raise OsmException(f'Error while loading data from: {url} {str(sys.exc_info()[1])}'  )
        
        return response.status_code, response.json()

       
    def checkServer(self, mode='matrix'):
        ok=False
        api_key=None
        payload=None

        coords = [ [13.782705, 52.824499], [ 13.780112, 52.822875] ] #[[13.632318,52.319139],[13.63223,52.31952]]
        profile = 'foot-walking' #'driving-car'

        
        if mode=='matrix':
            if self.__conf['servers']['matrix'][0]['type']=='osrm':
                query = self.__conf['servers']['matrix'][0]['url']+'/driving/13.632318,52.319139;13.63223,52.31952'
            else:
                payload = { 'locations': coords, 'metrics': ['distance'] }
                #query = self.__conf['servers']['matrix'][0]['url']+'/driving-car'
                query = self.__conf['servers']['matrix'][0]['url']+f'/{profile}'
                if 'api_key' in self.__conf['servers']['matrix'][0]:
                    api_key=self.__conf['servers']['matrix'][0]['api_key']

        elif mode=='routing':
            if self.__conf['servers']['matrix'][0]['type']=='osrm':
                query = self.__conf['servers']['routing'][0]['url']+'/driving/13.632318,52.319139;13.63223,52.31952' 
            else:
                payload = { 'coordinates': coords,
                            'instructions': 'false',
                            'geometry_simplify': 'true' 
                          }
                #query = self.__conf['servers']['routing'][0]['url']+'/driving-car/geojson'
                query = self.__conf['servers']['routing'][0]['url']+f'/{profile}/geojson'
                if 'api_key' in self.__conf['servers']['routing'][0]:
                    api_key=self.__conf['servers']['routing'][0]['api_key']

        elif mode=='geocoding':
            if self.__conf['servers']['geocoding'][0]['type']=='photon':
                query = self.__conf['servers']['geocoding'][0]['url']+'/api/?q=15745,Wildau,Hochschulring,1&limit=1&osm_tag=!boundary'
            else:
                query = self.__conf['servers']['geocoding'][0]['url']+'/search?q=15745,Wildau,Hochschulring,1&format=jsonv2'
      
        try:
            status, data = self.__openUrl(query, payload=payload, api_key=api_key, timeOutConnect=1)
            if status==200:
                ok = True
                self.__log.logging('check-'+mode,self.__conf['servers'][mode][0]['url'],'ok')
            else:
                self.__log.logging('check-'+mode,self.__conf['servers'][mode][0]['url'],'failed')
        except :
            ok = False
            self.__log.logging('check-'+mode,self.__conf['servers'][mode][0]['url'],'failed')
        
        return ok

   
    def openUrl(self, payload={}, params={}, mode = 'matrix' ):
        tries=0
        
        while True:
            if mode.startswith('geo'):
                tmpMode='geocoding'
            else:
                tmpMode=mode

            if tries==0 and self.__conf['isMainServer'][tmpMode]:
                server = self.__conf['servers'][tmpMode][0]
            else:
                server = self.__getServerSubstitute(tmpMode)
                self.__conf['isMainServer'][tmpMode]=False

            url=None
            api_key=None

            tmpPayLoad=payload.copy()
            tmpParams=params.copy()

            try:
                if mode=='matrix': 
                
                    if server['type']=='osrm':
                        path=";".join([",".join([ str(e) for e in row]) for row in payload['locations']]) 
                        if payload['travelmode']=='car':
                            profile='driving'
                        else:
                            raise OsmException(f"Travel type {payload['travelmode']} has not been implemented yet"  )
                    
                        url=server['url']+'/'+profile+'/'+path
                        url+='?sources='+";".join( str(x) for x in payload['sources'])
                        url+='&destinations='+";".join( str(x) for x in payload['destinations'])
                        url+='&fallback_coordinate=snapped&annotations=distance,duration'

                        tmpPayLoad=None

                    elif server['type']=='ors':
                        if payload['travelmode']=='car':
                            profile='driving-car'
                        elif payload['travelmode']=='foot':
                            profile='foot-walking'
                        elif payload['travelmode']=='wheelchair':
                            profile='wheelchair'
                        else:
                            raise OsmException(f"Travel type {payload['travelmode']} has not been implemented yet"  )
                        url = server['url']+'/'+profile
                        tmpPayLoad['metrics'] = ['distance','duration']
                        tmpPayLoad['units'] ='m'
                        del tmpPayLoad['travelmode']
                        if 'api_key' in self.__conf['servers']['matrix'][0]:
                            api_key=self.__conf['servers']['matrix'][0]['api_key']

                    else:
                        raise OsmException(f"Server type {server['type']} has not been implemented yet"  )
                    
                elif mode=='routing': 
                    if server['type']=='osrm':
                        path=";".join([",".join([ str(e) for e in row]) for row in payload['coordinates']]) 
                        if payload['travelmode']=='car':
                            profile='driving'
                        else:
                            raise OsmException(f"Travel type {payload['travelmode']} has not been implemented yet"  )
                        
                        url=server['url']+'/'+profile+'/'+path
                        url+='?geometries=geojson'
                        if payload['geometry_simplify'] == 'false':
                           url+='&overview=full' 
                        payload['instructions'] = 'false'  

                    elif server['type']=='ors':
                        if payload['travelmode']=='car':
                            profile='driving-car'
                        elif payload['travelmode']=='foot':
                            profile='foot-walking'
                        elif payload['travelmode']=='wheelchair':
                            profile='wheelchair'
                        else:
                            raise OsmException(f"Travel type {payload['travelmode']} has not been implemented yet"  )
                        url = server['url']+'/'+profile+'/geojson'
                        tmpPayLoad['instructions'] = 'false'
                        tmpPayLoad['radiuses'] = [-1]
                        del tmpPayLoad['travelmode']
                        if 'api_key' in self.__conf['servers']['routing'][0]:
                            api_key=self.__conf['servers']['routing'][0]['api_key']

                elif mode=='geoCoords':
                    if server['type']=='photon':
                        url = server['url']+'/api'
                        tmpParams['limit'] = '1'
                        tmpParams['osm_tag']='!boundary'
                    elif server['type']=='nominatim':
                        url = server['url']+'/search'
                        tmpParams['format'] = 'jsonv2'
                        tmpParams['limit'] = '1'
                
                elif mode=='geoSearch':
                    if server['type']=='photon':
                        url = server['url']+'/api'
                    elif server['type']=='nominatim':
                        url = server['url']+'/search'
                        tmpParams['format'] = 'jsonv2'
                        tmpParams['addressdetails']= '1'
                
                elif mode=='geoReverse':
                    if server['type']=='photon':
                        url = server['url']+'/reverse'
                    elif server['type']=='nominatim':
                        url = server['url']+'/reverse'
                        tmpParams['format'] = 'jsonv2'
                        tmpParams['addressdetails']= '1'

                if len(url)>1900:
                    raise OsmException(f'Url to long: {url}')
                          
                status, data = self.__openUrl(url,payload=tmpPayLoad, api_key=api_key, params=tmpParams)

                if status==200:
                    self.__log.logging(mode,server['url'],'ok')
                else: 
                    self.__log.logging(mode,server['url'],'failed')

                return server['type'], status, data

            except :
                tries += 1
                self.__log.logging(mode,server['url'],'failed')

                if tries==self.__conf['maxUrlTries']:
                    e=sys.exc_info()[0]
                    raise OsmException(f"Something went wrong while getting OSM data: {str(e)} for server {server['url']}")
                
        

    def __getServerSubstitute(self, mode):
        sLen = len(self.__conf['servers'][mode])

        if sLen==1:
            pos=0
        else:
            pos=random.randint(1,sLen-1)

        return self.__conf['servers'][mode][pos]


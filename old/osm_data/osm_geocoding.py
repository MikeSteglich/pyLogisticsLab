#***********************************************************************
 #  This code is part of pyLogisticsLab
 #
 #  Copyright (C) 2019 -
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

from urllib.error import URLError
from .osm_exception import *
from .osm_server import *

import urllib.request as url
import urllib.parse

import codecs
import re
import ssl
import sys
from io import StringIO
import json
import math

import random as rand

import traceback

class Geocoding:
    def __init__(self, optFile=None):
        self.__osmServer = OsmServer(optFile) 
        self.__addresses = []
        
        self.__maxUrlTries = 5

          

    def __openUrl(self, query ):

        tries=0
        proxyEnv = url.getproxies()
        if not self.__osmServer.httpProxy:
            if proxyEnv:
                if 'http' in proxyEnv:
                   self.__osmServer.httpProxy = proxyEnv['http']
        if not self.__osmServer.httpsProxy:
            if proxyEnv:
                if 'https' in proxyEnv:
                   self.__osmServer.httpsProxy = proxyEnv['https']

        while True:
            if tries==0:
                server = self.__osmServer.photonMain
            else:
                server = self.__getServerSubstitute()
           
            finalQuery = server + query

            try:
               
                req = url.Request(finalQuery)
                if self.__osmServer.httpProxy or self.__osmServer.httpsProxy:
                    if self.__osmServer.httpProxy:
                        req.set_proxy(self.__osmServer.httpProxy.replace('http://','').replace('https://','').strip(), 'http' )
                    if self.__osmServer.httpsProxy:
                        req.set_proxy(self.__osmServer.httpsProxy.replace('http://','').replace('https://','').strip(), 'https' )
                
                #req.add_header('Upgrade-Insecure-Requests', '1')
                #req.add_header('Accept-Encoding', 'gzip, deflate, sdch, br')
                #req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36')
                #req.add_header('Connection', 'keep-alive')
                #req.add_header('Cache-Control', 'max-age=0')
                req.add_header('Accept-Language', 'en-US,en;q=0.8,pt;q=0.6')
                #req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

                data = url.urlopen(req, context=ssl.SSLContext())
                return data
            except URLError as e:
                tries += 1
                
                if tries==self.__maxUrlTries:
                    print(sys.exc_info())
                    print(", ".join(traceback.format_list(traceback.extract_stack())))
                    raise OsmException(f"Something went wrong while getting OSM data: {str(e)}")

    def __getServerSubstitute(self):
        sLen=0
        sLen=len(self.__osmServer.photonSubstitutes) 
        if sLen==1:
            pos=0
        else:
            pos=rand.randint(0,sLen-1)

        serverSubstiute=self.__osmServer.photonSubstitutes[pos]
      
        return serverSubstiute.strip()




    def getAdress(self):
        return self.__addresses[0]

    address = property(getAdress)

    def getAdresses(self):
        return self.__addresses

    addresses = property(getAdresses)

    def getAddresses(self, searchString=None, coords=None ):

        self.__addresses=[]

        if not searchString and not coords:
            raise OsmException("Either search string or coordinates required")
        
        if searchString and type(searchString) != str :
            raise OsmException("Wrong search string: string required instead of "+str(type(searchString)))

        if coords:
            if type(coords) != list:
                raise OsmException("Wrong coordinates: list of float required instead of "+str(type(coords)))
            if len(coords) != 2:
                raise OsmException("Wrong coordinates: list of two floats required")
            if type(coords[0]) != float or type(coords[1]) != float:
                raise OsmException("Wrong coordinates: list of float required instead of "+str(type(coords)))

        if searchString:
            query = "/api/?q="+urllib.parse.quote( searchString)

        if coords:
            query = f"/reverse/?lat={coords[0]}&lon={coords[1]}" 

        print('Loading address list from OpenStreetMap via Photon has been started.')
    
       
        if len(query)>1900:
            raise OsmException("Url to long: "+ query)
        
        gisData = self.__openUrl(query)

        if not gisData:
            raise OsmException('Something went wrong while getting OSM coordinates ')
        gisJson = json.load(gisData)

        try:
            if gisJson['features']:

                for e in gisJson['features']:
                    if 'street' in e['properties'] and 'city' in e['properties']:
                        tmpList =[]
                        tmpList = e['geometry']['coordinates']
                        if 'name' in e['properties']: 
                            tmpList.append( e['properties']['name'])
                        else:
                            tmpList.append( '' )

                        tmpList.append(e['properties']['city'])
                        tmpList.append(e['properties']['postcode'])

                        tmpStreet = e['properties']['street']
                        if 'housenumber' in e['properties']:
                            tmpStreet +=  ' ' +e['properties']['housenumber']
                        tmpList.append(tmpStreet)

                        tmpList.append(e['properties']['country'])
                        tmpList.append(e['properties']['countrycode'])

                        self.__addresses.append(tmpList)

                print(f' ... done: {len(self.__addresses)} have been found')
            else:
                print(f" ... no address data have been found")
        except:
            print(f" ... something went wrong while getting addresses for search string {self.__searchStr}")
              
          

    


    


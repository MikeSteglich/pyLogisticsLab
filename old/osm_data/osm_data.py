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
from  .osm_nodes import *

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

#from pathlib import Path
#import os

OSM_EXACT = 1000
OSM_UNEXACT = 1001

OSRM_QUERY = 2000
NOMINATIM_QUERY = 2001
PHOTON_QUERY = 2002



class Data:
    def __init__(self, nodes=None, coords=None, optFile=None):

        if nodes:
            if str(type(nodes)) != "<class 'osm_data.osm_nodes.Nodes'>":
                raise OsmException("Wrong nodes : osm_data.osm_nodes.Nodes expected instead of: " + str(type(nodes)))
            self.__nodes = nodes

        self.__osmServer = OsmServer(optFile) 

        self.__beeLineDistances = []
        self.__distMatrix = []
        self.__durasMatrix = []
        if coords:
            self.setCoords(coords)
        else:
            self.__coordinates = []

        self.__requests = []
        self.__maxNodesInMatrix = 100
        self.__maxNodesInRoute = 250

        self.__nrOfNodes = 0
        self.__status = OSM_EXACT

        self.__maxUrlTries = 5
        #self.__urlTimeOut = 2

        #logName = str(Path.home())+os.sep+'logisticsLabOsm.log'
        #self.__logFile = open(logName, 'w')
        #self.__logFile.write('start\n')
        
      
    #def __del__(self):
    #    self.__logFile.close()


    def __checkCoodinate(self, lat, lon): 
        if not ( isinstance(lat, (float, int) ) and isinstance(lat, (float,int)) ):
            raise OsmException(f'Wrong type for coordinate: ({lat};{lon}) - ({type(lat)},{type(lon)}) - (float,float) expected ')
        if not (abs(lat)<=90 and abs(lon)<= 180):
            raise OsmException(f'Wrong coordinate: ({lat};{lon})')

    def __checkDistances(self):
        self.__status = OSM_EXACT
        self.__greatCircleDistance()
        sDistOsm = 0
        sDistGc = 0
        sTime = 0

        pIndices = []

        for i,row in enumerate(self.__distMatrix):
            for j, dist in enumerate(row):
                if dist!=None: 
                    if dist == 0:
                        if self.__coordinates[i]!=self.__coordinates[j]:
                            pIndices.append((i,j))
                    else:
                        if dist < self.__beeLineDistances[i][j] :
                            pIndices.append([i,j])
                        else:
                            sDistGc += self.__beeLineDistances[i][j]
                            sDistOsm += dist
                            sTime += self.__durasMatrix[i][j]
                else:
                    pIndices.append([i,j])
                    
        
        detourFactor = sDistOsm/sDistGc
        timeFactor = sTime/sDistGc
        for i,j in pIndices:
            self.__distMatrix[i][j] = self.__beeLineDistances[i][j] * detourFactor
            self.__durasMatrix[i][j] = self.__beeLineDistances[i][j] * timeFactor

        if len(pIndices)>0:
            self.__status = OSM_UNEXACT

        for i,row in enumerate(self.__durasMatrix):
            for j, tTime in enumerate(row):
                if i!=j and tTime==0:
                   self.__durasMatrix[i][j] = self.__beeLineDistances[i][j] * timeFactor
       

    def __greatCircleDistance(self):
        for i, c1 in enumerate(self.__coordinates):
            tmpDist = []
            for j, c2 in enumerate(self.__coordinates):
                if i==j :
                    tmpDist.append(0)
                else:
                    lat1, lon1 = self.__coordinates[i] 
                    lat2, lon2 = self.__coordinates[j] 
                    dlat = math.radians(lat2-lat1)
                    dlon = math.radians(lon2-lon1)
                    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1))* math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    tmpDist.append( 6378.137 * c * 1000)
            self.__beeLineDistances.append(tmpDist)   

    def __createRequestList(self):
        maxNodes = self.__maxNodesInMatrix
        nrOfSteps = math.ceil(self.__nrOfNodes/maxNodes)
        if nrOfSteps>1:
            if (self.__nrOfNodes-maxNodes*(nrOfSteps-1)==1):
                maxNodes-=1
        maxNodes2 = int(maxNodes/2)
       
        self.__requests  = []
        nodes = list(range(self.__nrOfNodes))

        oldRestNodes=[]

        for s in range(nrOfSteps):
            subNodes = nodes[s*maxNodes:(s+1)*maxNodes]
            if subNodes!=oldRestNodes:
                restNodes = nodes[(s+1)*maxNodes:] 
                oldRestNodes=restNodes

                self.__requests.append(subNodes)

                for i,startNode in enumerate(subNodes[::maxNodes2]) :
                    for j,restStartNode in enumerate(restNodes[::maxNodes2]):
                        subNodes1 = subNodes[i*maxNodes2:(i+1)*maxNodes2] + restNodes[j*maxNodes2:(j+1)*maxNodes2]
                        self.__requests.append(subNodes1)
                

    def __initMatrices(self):
        self.__nrOfNodes = len(self.__coordinates)
        self.__distMatrix = [ [ 0 for i in range(self.__nrOfNodes)]  for j in range(self.__nrOfNodes)]
        self.__durasMatrix = [ [ 0 for i in range(self.__nrOfNodes)]  for j in range(self.__nrOfNodes)]
        

    def __openUrl(self, query, mode = PHOTON_QUERY ):

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
            if mode == NOMINATIM_QUERY:
                if tries==0:
                    server = self.__osmServer.nominatimMain
                else:
                    server = self.__getServerSubstitute(mode)
            elif mode == PHOTON_QUERY:
                if tries==0:
                    server = self.__osmServer.photonMain
                else:
                    server = self.__getServerSubstitute(mode)
            else:
                if tries==0:
                    server = self.__osmServer.osrmMain
                else:
                    server = self.__getServerSubstitute(mode)
            finalQuery = server + query

            try:
                #self.__logFile.write(finalQuery+'\n')

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

    def __getServerSubstitute(self, mode):
        sLen=0
        if mode == NOMINATIM_QUERY:
            sLen=len(self.__osmServer.nominatimSubstitutes)
        elif mode == PHOTON_QUERY:
            sLen=len(self.__osmServer.photonSubstitutes) 
        else:
            sLen=len(self.__osmServer.osrmSubstitutes) 
        
        if sLen==1:
            pos=0
        else:
            pos=rand.randint(0,sLen-1)

        serverSubstiute=''
        if mode == NOMINATIM_QUERY:
            serverSubstiute=self.__osmServer.nominatimSubstitutes[pos]
        elif mode == PHOTON_QUERY:
            serverSubstiute=self.__osmServer.photonSubstitutes[pos]
        else:
            serverSubstiute=self.__osmServer.osrmSubstitutes[pos]

        return serverSubstiute.strip()


    @property
    def status(self):
        return self.__status

    def getDistancematrix(self):
        return self.__distMatrix

    distanceMatrix = property(getDistancematrix)

    def getTimeMatrix(self):
        return self.__durasMatrix

    timeMatrix = property(getTimeMatrix)

    
    def getDistTimeData(self, travelmode='car'):

        self.__initMatrices()
        self.__createRequestList()

        if travelmode not in ('car','bike','foot'):
            raise OsmException(f"Wrong travelmode {travelmode} - 'car', 'bike' or 'foot' expected.")

        mainQuery = '/table/'+self.__osmServer.osrmVersion+'/'+travelmode+'/'
        
        if not self.__coordinates:
            raise OsmException("No coordinates available. Cannot generate distance or time matrix ")

        try:
            rIdx = 1
            for rNodes in self.__requests:
                dists = []
                duras = []
                coords = []

                query = mainQuery

                for i in rNodes:
                    coords.append( self.__coordinates[i] )

                query += ';'.join( [ ','.join(  [ str(e[1]) , str(e[0]) ] ) for e in coords     ] )
                query += '?fallback_coordinate=snapped&annotations=duration,distance'

                if len(query)>1900:
                    raise OsmException("Url to long: "+ query)

                gisData = self.__openUrl(query, mode=OSRM_QUERY)
                
                if not gisData:
                    raise OsmException('Something went wrong while getting OSM distances ')
                gisJson = json.load(gisData)

                if gisJson['code'].lower()!='ok':
                    raise OsmException('Something went wrong while getting OSM distances :' +gisJson['message']) 

                dists =  gisJson['distances']
                duras =  gisJson['durations']

                for i,ii in enumerate(rNodes):
                    for j,jj  in enumerate(rNodes):
                        self.__distMatrix[ii][jj] = dists[i][j]
                        self.__durasMatrix[ii][jj]  = duras[i][j]

                print( f' ... request {rIdx} of {len(self.__requests)}')
                rIdx +=1 

            self.__checkDistances()

        except OsmException as e:
            raise OsmException(e.msg)
        except:
            raise OsmException('Something went wrong while getting OSM data: ' + str(sys.exc_info()[0]))

  
    def getCoordinates(self):
        try:
            return self.__getCoordinatesPhoton()
        except OsmException as e:
            print(e.msg)
            return self.__getCoordinatesNominatim()

    def __getCoordinatesPhoton(self):
        try:
            print('Loading coordinates from OpenStreetMap via Photon has been started.')
    
            mainQuery = "/api/?q="

            for idx,node in enumerate(self.__nodes.nodes):
                query = mainQuery

                query += urllib.parse.quote( node.city  ) #+","+urllib.parse.quote(node.country)+","+urllib.parse.quote(node.street)+","+urllib.parse.quote(node.postalcode )
                if node.postalcode:
                    query += ","+urllib.parse.quote(node.postalcode )
                
                if node.street:
                    query += ","+urllib.parse.quote(node.street)
                
                if node.country:
                    query += ","+urllib.parse.quote(node.country)
              
                if node.state:
                    query += ","+urllib.parse.quote(node.state)
                
                query += "&limit=1&osm_tag=!boundary&lang=en"
                if len(query)>1900:
                    raise OsmException("Url to long: "+ query)

                gisData = self.__openUrl(query, mode=PHOTON_QUERY)

                if not gisData:
                    raise OsmException('Something went wrong while getting OSM coordinates ')
                gisJson = json.load(gisData)

                try:
                    node.lat = float(gisJson['features'][0]['geometry']['coordinates'][1])
                    node.lon = float(gisJson['features'][0]['geometry']['coordinates'][0])
                    print(f' ... node {idx+1} {node.city} {node.country} {node.street}')
                except:
                    node.lat = 0
                    node.lon = 0
                    print(f" ... something went wrong while getting OSM coordinates for node {idx+1} {node.city} {node.country} {node.street}")
              
                self.__coordinates.append( (node.lat, node.lon))
             
            print('Coordinates have been loaded')
            return self.__coordinates

        except OsmException as e:
            raise OsmException(e.msg)
        except:
            raise OsmException('Something went wrong while getting OSM coordinates : ' + str(sys.exc_info()))


    def __getCoordinatesNominatim(self):
        try:
            print('Loading coordinates from OpenStreetMap via Nominatim has been started.')
            mainQuery = "/search?"

            for idx,node in enumerate(self.__nodes.nodes):
                query = mainQuery
                query += "city="+urllib.parse.quote(node.city)
                if node.country:
                    query += "&country="+urllib.parse.quote(node.country)
                if node.street:
                    query += "&street="+urllib.parse.quote(node.street)
                if node.postalcode:
                    query += "&postalcode="+urllib.parse.quote(node.postalcode)
                if node.county:
                    query += "&county="+urllib.parse.quote(node.county)
                if node.state:
                    query += "&state="+urllib.parse.quote(node.state)
                query+="&format=jsonv2"
               
                if len(query)>1900:
                    raise OsmException("Url to long: "+ query)

                gisData = self.__openUrl(query, mode=NOMINATIM_QUERY)

                if not gisData:
                    raise OsmException('Something went wrong while getting OSM coordinates ')
                gisJson = json.load(gisData)

                try:
                    node.lat = float(gisJson[0]['lat'])
                    node.lon = float(gisJson[0]['lon'])
                    print(f' ... node {idx+1} {node.city} {node.country} {node.street}')
                except:
                    node.lat = 0
                    node.lon = 0
                    print(f" ... something went wrong while getting OSM coordinates for node {idx+1} {node.city} {node.country} {node.street}")
           
                self.__coordinates.append( (node.lat, node.lon))
             
            print('Coordinates have been loaded')
            return self.__coordinates

        except OsmException as e:
            raise OsmException(e.msg)
        except:
            raise OsmException('Something went wrong while getting OSM coordinates : ' + str(sys.exc_info()))


    def getCoords(self):
        return self.__coordinates

    def setCoords(self, coords):
        self.__coordinates = []
        if not isinstance(coords,(list,tuple)):
            raise OsmException(f'Wrong type of the list of coordinates : {type(coords)} - list or tuple excepted')
        
        try:
            for lat,lon in coords:
                self.__checkCoodinate(lat, lon)
                self.__coordinates.append( (lat, lon))
        except OsmException as e:
            raise OsmException(e.msg)
        except:
            raise OsmException(f'Wrong coordinates' +  str(sys.exc_info()[0]))
               

    coordinates = property(getCoords, setCoords)


    def getRoute(self, coords = None, nodes = Nodes, travelmode='car', details='full' ):
        
        try:
            
            if travelmode not in ('car','bike','foot'):
                raise OsmException(f"Wrong travelmode {travelmode} - 'car', 'bike' or 'foot' expected.")

            if not (coords or nodes):
                raise OsmException('Either list of coordinates or nodes are expected to get a route')

            if coords:
                if not isinstance(coords, list):
                    raise OsmException(f'Wrong coordinates: a list of coordinates has been expected instead of: {type(coords)} ')
                
                for c in coords:
                    if not isinstance(c, (tuple, list)):
                        raise OsmException(f'Wrong coordinate: {c} ')
                    if len(c)!=2:
                         raise OsmException(f'Wrong coordinate: {c} ')
                    self.__checkCoodinate(c[0], c[1])
                
                allCoords=coords
                       
                    
            elif nodes: 
                allCoords=[]
                if not isinstance(nodes, list):
                    raise OsmException(f'Wrong nodes: a list of nodes has been expected instead of: {type(nodes)} ')
                
                if not self.__coordinates:
                    raise OsmException(f'No coordinates available')

                for n in nodes:
                    if not isinstance(n, int):
                        raise OsmException(f'Wrong node index: {n} ')
                    
                    if n<0 or n>=len(self.__coordinates):
                        raise OsmException(f'Wrong node index: {n}, 0 <= index <= {len(self.__coordinates)} ')

                    allCoords.append(self.__coordinates[n])

            nrOfRequests=math.ceil(len(allCoords)/self.__maxNodesInRoute)   

            route = []
            mainQuery =  '/route/'+self.__osmServer.osrmVersion+'/'+travelmode+'/'

            for rIdx in range(nrOfRequests):     

                if rIdx == 0:
                    coords = allCoords[rIdx*self.__maxNodesInRoute:(rIdx+1)*self.__maxNodesInRoute]
                    
                else:
                    coords = allCoords[rIdx*self.__maxNodesInRoute-1:(rIdx+1)*self.__maxNodesInRoute]

                query = mainQuery

                nrOfCoords = len(coords)    
                for i,(lat,lon) in enumerate(coords):
                    query += str(lon) + "," + str(lat)  
                    if i < nrOfCoords-1: 
                        query +=";"   
                if details=='full':
                    query += "?geometries=geojson&overview=full"
                else: 
                    query += "?geometries=geojson"
                gisData = self.__openUrl(query, mode=OSRM_QUERY)
                if not gisData:
                    raise OsmException('Something went wrong while getting OSM route ')
                gisJson = json.load(gisData)

                if gisJson['code'].lower()!='ok':
                    raise OsmException('Something went wrong while getting OSM route :' +gisJson['message']) 

                tmpRoute = gisJson['routes'][0]['geometry']['coordinates']

                for leg in tmpRoute:
                    try:
                        route.append( (float(leg[1]),float(leg[0]) ) )
                    except:
                        raise OsmException('Something went wrong while getting OSM route : ' + str(sys.exc_info()))
           
        except OsmException as e:
            raise OsmException(e.msg)
        except:
            raise OsmException('Something went wrong while getting OSM route : ' + str(sys.exc_info()))

        return route



    


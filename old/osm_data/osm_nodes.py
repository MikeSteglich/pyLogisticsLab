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

from .osm_exception import *
import sys

class Node:
    def __init__(self, address) :
        
        if not address:
            raise OsmException('Something went wrong while adding a new node ')

        self.__city = None
        self.__country = None
        self.__street = None
        self.__postalcode = None
        self.__county = None
        self.__state = None
        self.__lat = None
        self.__lon = None

        for i,e in enumerate(address):
            entry = e.strip()
            if i==0:
                self.__city=entry
            elif i==1:
                self.__country=entry
            elif i==2:
                self.__street=entry
            elif i==3:
                self.__postalcode=entry
            elif i==4:
                self.__county=entry
            elif i==5:
                self.__state=entry
            elif i==5:
                try:
                    lat =  float(entry)
                    if  not (abs(lat)  <= 90):
                        raise OsmException(f'Wrong latitude: {entry} ')
                except:
                    raise OsmException(f'Wrong latitude: {entry} ')
                self.__lat=lat
            elif i==6:
                try:
                    lon =  float(entry)
                    if not (abs(lon) <= 180):
                        raise OsmException(f'Wrong latitude: {entry} ')
                except:
                    raise OsmException(f'Wrong latitude: {entry} ')
                self.__lon=lon   

      
    def getCity(self):
        return self.__city
    city = property(getCity)
      
    def getCountry(self):
        return self.__country
    country = property(getCountry)

    def getStreet(self):
        return self.__street
    street = property(getStreet)

    def getPostalcode(self):
        return self.__postalcode
    postalcode = property(getPostalcode)

    def getCounty(self):
        return self.__county
    county = property(getCounty)
                
    def getState(self):
        return self.__state
    state = property(getState)

    def setLon(self, lon):
        self.__lon=lon
    
    def getLon(self):
        return self.__lon
    
    lon = property(getLon,setLon )

    def setLat(self, lat):
        self.__lat=lat
    
    def getLat(self):
        return self.__lat
    
    lat = property(getLat,setLat )
                    

# *************** Node *************************************
class Nodes:
    # *********** constructor **********
    def __init__(self, addressFile=None, addressList=None):
        if addressFile:
            try:
                addresses = [line.strip() for line in open('addresses.txt', encoding='utf-8')]
            except:
                raise OsmException('Something went wrong while reading addresses: '+str(sys.exc_info()[0]))
            
            self.__addresses = []

            for a in addresses:
                if not a.strip().startswith('#') and a.strip():
                    self.__addresses.append( Node( a.split(',') ))

        elif addressList:
            if not isinstance(addressList, (list,tuple)):
                raise OsmException("Wrong addresses : list/tuple of list/tuples of strings expected instead of: " + str(type(addressList)))
            if not isinstance(addressList[0], (list,tuple)):
                raise OsmException("Wrong address :  list of strings expected instead of: " + str(type(addressList[0])))
        
            self.__addresses = []
            for a in addressList:
                self.__addresses.append( Node( a ))      
  
    
    def add(self, city = None, country = None , street = None, postalcode = None , county = None, state = None, lat = None, lon = None):
        self.__addresses.append([city,county,street,postalcode,county,state, lat, lon ])


    @property
    def nodes(self):
        return self.__addresses


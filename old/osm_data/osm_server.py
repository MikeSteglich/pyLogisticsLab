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

class OsmServer:
    def __init__(self, optFile=None):

        self.nominatimMain = 'https://nominatim.openstreetmap.org'
        self.nominatimSubstitutes = ['https://nominatim.openstreetmap.org']

        self.osrmMain = 'http://osm1.th-wildau.de:5000'
        self.osrmSubstitutes = ['https://routing.openstreetmap.de/routed-car','https://router.project-osrm.org']

        self.photonMain = 'http://osm2.th-wildau.de:2322'
        self.photonSubstitutes = ['https://photon.komoot.io']

        self.osrmVersion = 'v1'

        #self.httpProxy = 'http://proxy.th-wildau.de:8080'
        #self.httpsProxy = 'http://proxy.th-wildau.de:8080'
        self.httpProxy = ''
        self.httpsProxy = ''

        self.__optFile = optFile

        if optFile:
            self.__readOptFile()


    def __readOptFile(self):
        try:
            optFile = open(self.__optFile, 'r')
            optLines = optFile.readlines()
            optFile.close()

            for opt in optLines:
                if not opt.strip():
                    continue
                                
                if opt.strip()[0]=='#' or opt.strip()[0]=='\n' or opt.strip()[0]=='\r':
                    continue

                o = opt.split('=')
                key = o[0].strip().upper()
                vals = o[1].split(',')

                if key=='NOMINATIM':
                    if len(vals)>1:
                        self.nominatimSubstitutes = []
                    for i,val in enumerate(vals):
                        val = val.strip()
                        if i==0:
                            self.nominatimMain = val
                        else:
                            self.nominatimSubstitutes.append(val)
                
                elif key=='OSRM':
                    if len(vals)>1:
                        self.osrmSubstitutes = []
                    for i,val in enumerate(vals):
                        val = val.strip()
                        if i==0:
                            self.osrmMain = val
                        else:
                            self.osrmSubstitutes.append(val)

                elif key=='PHOTON':
                    if len(vals)>1:
                        self.photonSubstitutes = []
                    for i,val in enumerate(vals):
                        val = val.strip()
                        if i==0:
                            self.photonMain = val
                        else:
                            self.photonSubstitutes.append(val)
                
                elif key=='OSRMVERSION':
                    if len(vals)>=1:
                        self.osrmVersion = vals[0].strip()

                elif key=='HTTPPROXY':
                    if len(vals)>=1:
                        self.httpProxy = vals[0].strip()
                elif key=='HTTPSPROXY':
                    if len(vals)>=1:
                        self.httpsProxy = vals[0].strip()

        except:
            raise OsmException("Internal error while reading option file: " + str(sys.exc_info()[1]))

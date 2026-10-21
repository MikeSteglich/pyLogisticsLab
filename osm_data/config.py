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
from .logging import *
from .scheduler import *
from .tools import *

import yaml
import requests
import os
import sys

from datetime import datetime


# defaults as logisticsLabCore.paths: LOGLAB_CONF_DIR or <project>/confs, LOGLAB_LOG_DIR or <project>/logs
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def defaultOptFile():
    """ logisticsLab.local.yml (own servers, api keys) if it exists, otherwise logisticsLab.yml (TH Wildau) """
    confDir = os.environ.get('LOGLAB_CONF_DIR') or os.path.join(_PROJECT_DIR, 'confs')
    local = os.path.join(confDir, 'logisticsLab.local.yml')
    return local if os.path.isfile(local) else os.path.join(confDir, 'logisticsLab.yml')

def defaultLogFile():
    logDir = os.environ.get('LOGLAB_LOG_DIR') or os.path.join(_PROJECT_DIR, 'logs')
    os.makedirs(logDir, exist_ok=True)
    return os.path.join(logDir, 'logisticsLab.log')


class Config:
    def __init__(self, optFile=None, logFile=None):
        self.__conf={}
        self.__optFile=optFile
        if not optFile:
            self.__optFile=defaultOptFile()
            
        self.__readOptFile()

        if logFile:
            self.__conf['logFile']=logFile
        elif not self.__conf.get('logFile'):
            self.__conf['logFile']=defaultLogFile()

        self.__log = Logging(self.__conf['logFile'],self.__conf['logging'])
        self.__log.logging('config',('loaded from mainConfig' if self.__conf['isMainConfig'] else 'local'),'OK')

        self.__scheduler = Scheduler(self.__conf, self.__log) 

        self.__conf['isMainServer']={}
        
        for m in ['matrix', 'routing', 'geocoding']: 
            self.__conf['isMainServer'][m] = self.__scheduler.checkServer(m)
        
        
        dumpConf(self.__conf)

        del self.__scheduler
        del self.__log

    def getConf(self):
        return self.__conf
    conf = property(getConf)

    def __readOptFile(self):
        try:
            optFile = open(self.__optFile, 'r')
            self.__conf= yaml.safe_load(optFile)
            self.__conf['isMainConfig']=False

            if not 'proxies' in self.__conf:
                proxies=requests.utils.getproxies()
                if proxies:
                    self.__conf['proxies']=proxies

            try:
                if 'main_configuration' in self.__conf:
                    if not 'proxies' in self.__conf:
                        response=requests.get(self.__conf['main_configuration'], timeout=(3,10))
                    else: 
                        response=requests.get(self.__conf['main_configuration'], proxies=self.__conf['proxies'],timeout=(3,10))
                    if response.status_code==200:
                        mainConf=yaml.safe_load(response.text)
                        if 'servers' in mainConf:
                            self.__conf['servers']=mainConf['servers']
                            self.__conf['isMainConfig']=True
                        else:
                            self.__conf['isMainConfig']=False
            except:
                #print (str(sys.exc_info()))
                self.__conf['isMainConfig']=False

            if not 'maxUrlTries' in self.__conf:
                self.__conf['maxUrlTries'] = 5

            if not 'maxTableSize' in self.__conf['servers']:
                self.__conf['servers']['maxTableSize']=2500
            
            if not 'maxNodesInRoute' in self.__conf['servers']:
                self.__conf['servers']['maxNodesInRoute']=50

            if not 'logging' in self.__conf:
                self.__conf['logging'] = False

            for s in self.__conf['servers']['matrix']:
                if s['type'] not in ('ors','osrm'):
                    raise OsmException(f'Server type {s["type"]} has not been implemented yet'  )
                
            for s in self.__conf['servers']['routing']:
                if s['type'] not in ('ors','osrm'):
                    raise OsmException(f'Server type {s["type"]} has not been implemented yet'  )
                
            for s in self.__conf['servers']['geocoding']:
                if s['type'] not in ('photon','nominatim'):
                    raise OsmException(f'Server type {s["type"]} has not been implemented yet'  )

        except:
            raise OsmException(f'Internal error while reading option file: {str(sys.exc_info()[1])}'  )

    
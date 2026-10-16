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

from exception import *
import osm_data as osm

import yaml
import sys
import os

class Config:
    def __init__(self, optFile=None):
        self.__conf={}

        if optFile:
            self.__optFile=optFile
        else:
            self.__optFile='logisticsLabServer.yml'
            
        self.__readOptFile()

        #service thread mit check aller xxx minuten
        osm.Config(optFile='logisticsLab.yml', logFile=self.__conf['osmLogFile'])

  
    def getConf(self):
        return self.__conf
    conf = property(getConf)

    def __readOptFile(self):
        try:
            optFile = open(self.__optFile, 'r')
            self.__conf= yaml.safe_load(optFile)
               
            if not 'port' in self.__conf:
                self.__conf['port'] = 5000

            if not 'maxProblems' in self.__conf:
                self.__conf['maxProblems']=4

            if not 'maxInactivityTime' in self.__conf:
                self.__conf['maxInactivityTime']=43200
            
            if not 'serviceIntervall' in self.__conf:
                self.__conf['serviceIntervall']=30

            if not 'logging' in self.__conf:
                self.__conf['logging']=True

            if not 'debugging' in self.__conf:
                self.__conf['debugging']=True

            # log files are written to logPath (default: server directory) and not to the working directory
            if not self.__conf.get('logPath'):
                self.__conf['logPath']=os.path.dirname(os.path.abspath(__file__))
            os.makedirs(self.__conf['logPath'], exist_ok=True)

            if not 'logMaxBytes' in self.__conf:
                self.__conf['logMaxBytes']=5000000

            if not 'logBackupCount' in self.__conf:
                self.__conf['logBackupCount']=5

            self.__conf['logFile']=os.path.join(self.__conf['logPath'], 'logisticsLabServer.log')
            self.__conf['osmLogFile']=os.path.join(self.__conf['logPath'], 'logisticsLab.log')
            self.__conf['solverLogFile']=os.path.join(self.__conf['logPath'], 'HiGHS.log')

            for problemType in ['tsp', 'tpp']:
                if not self.__conf.get(problemType):
                    self.__conf[problemType]={}
                self.__conf[problemType]['solverLogFile']=self.__conf['solverLogFile']
            
            
        except:
            raise LogLabServerException(f'Internal error while reading option file: {str(sys.exc_info()[1])}'  )

    
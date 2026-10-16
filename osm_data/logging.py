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
from datetime import datetime


class Logging:
    def __init__(self, logfile=None, isLogging=True):
        if not logfile:
            self.__logFile='logisticsLab.log'
        else:
            self.__logFile=logfile
        if isLogging==True:
            self.__isLogging=True
        else:
            self.__isLogging=False
    
    def logging(self, mode, server, success):
        try:
            if self.__isLogging:
                with open( self.__logFile,'a', encoding='utf-8') as log:
                    log.write(f'{mode},{server},{datetime.now().date()},{datetime.now().time():%X},{success}\n') 
        except:
                print('cannot write log file')


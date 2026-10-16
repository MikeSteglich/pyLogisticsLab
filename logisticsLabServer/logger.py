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
import logging
import logging.handlers


class Logging:
    def __init__(self, logfile=None, isLogging=True, isDebugging=False, maxBytes=5000000, backupCount=5):
        if not logfile:
            self.__logFile='logisticsLabServer.log'
        else:
            self.__logFile=logfile

        if isLogging==True:
            self.__isLogging=True
        else:
            self.__isLogging=False

        if isDebugging==True:
            self.__isDebugging=True
        else:
            self.__isDebugging=False


        self.__logger = logging.getLogger("logisticsLabServerLogger")
        self.__logger.setLevel(logging.DEBUG)

        # only one handler per logger - otherwise every line is written several times
        if not self.__logger.handlers:
            self.__handler = logging.handlers.RotatingFileHandler(self.__logFile, maxBytes=maxBytes, backupCount=backupCount, encoding="utf-8")
            self.__formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            self.__handler.setFormatter(self.__formatter )
            self.__logger.addHandler(self.__handler)

    def __message(self, module, message):
        return f"{module} - {message}"

    def info(self, module, message):
        if self.__isLogging:
            self.__logger.info(  self.__message(module, message)  )

    def warning(self, module, message):
        if self.__isLogging:
            self.__logger.warning(  self.__message(module, message)  )

    def error(self, module, message):
        if self.__isLogging:
            self.__logger.error(  self.__message(module, message)  )

    def debug(self, module, message):
        if self.__isDebugging:
            self.__logger.debug(  self.__message(module, message)  )

import logging
import logging.handlers


class CoreLogger:
    """ logger with the interface used by the core: debug/info/warning/error(module, message)

        The server passes its own logger with the same interface.
    """
    def __init__(self, logFile=None, isDebugging=False, maxBytes=5000000, backupCount=5, name='logisticsLabCore'):
        self.__isDebugging = isDebugging
        self.__logger = logging.getLogger(name)
        self.__logger.setLevel(logging.DEBUG)
        self.__logger.propagate = False

        # only one handler per logger - otherwise every line is written several times
        if not self.__logger.handlers:
            if logFile:
                handler = logging.handlers.RotatingFileHandler(logFile, maxBytes=maxBytes, backupCount=backupCount, encoding='utf-8')
            else:
                handler = logging.NullHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.__logger.addHandler(handler)

    def info(self, module, message):
        self.__logger.info(f'{module} - {message}')

    def warning(self, module, message):
        self.__logger.warning(f'{module} - {message}')

    def error(self, module, message):
        self.__logger.error(f'{module} - {message}')

    def debug(self, module, message):
        if self.__isDebugging:
            self.__logger.debug(f'{module} - {message}')

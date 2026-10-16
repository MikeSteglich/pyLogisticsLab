#*************** LogLabCoreException ***************************
class LogLabCoreException(Exception):
    """ error in the data of a request or while solving - httpStatus classifies the error for the clients """
    def __init__(self, message, httpStatus=400):
        super().__init__(message)
        self.httpStatus = httpStatus
#*************** end LogLabCoreException ***********************


#*************** LogLabLimitException **************************
class LogLabLimitException(LogLabCoreException):
    """ a request is rejected because of a limit or missing rights """
    pass
#*************** end LogLabLimitException **********************

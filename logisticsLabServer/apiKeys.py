from exception import *

import datetime
import hashlib
import os
import secrets
import threading
import yaml


# services that can be granted to a key: all problem types and the geo services
SERVICES = ['tsp', 'tpp', 'matrix', 'routing', 'geocoding']


def hashKey(key):
    """ only the sha256 hash of a key is stored - keys are random, so a fast hash is sufficient """
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

def newKey():
    return secrets.token_urlsafe(32)


class ApiKey:
    """ an api key entry of the key file

        name             identifies the key in logs and owns the problems submitted with it
        hash             sha256 hash of the key
        expires          optional date, the key is invalid after this day
        allowed          optional list of services, default: all services
        maxOpenProblems  optional maximum number of waiting or running problems
        disabled         optional, True blocks the key
    """
    def __init__(self, entry, defaultMaxOpenProblems):
        if not isinstance(entry, dict) or not entry.get('name') or not entry.get('hash'):
            raise LogLabServerException(f'wrong api key entry {entry}')

        self.name = str(entry['name'])
        self.hash = str(entry['hash'])

        self.expires = entry.get('expires')
        if isinstance(self.expires, str):
            self.expires = datetime.date.fromisoformat(self.expires)

        self.allowed = entry.get('allowed') or list(SERVICES)
        for s in self.allowed:
            if s not in SERVICES:
                raise LogLabServerException(f'wrong service {s} for api key {self.name}')

        self.maxOpenProblems = int(entry.get('maxOpenProblems', defaultMaxOpenProblems))
        self.disabled = bool(entry.get('disabled', False))

    def isValid(self):
        if self.disabled:
            return False
        if self.expires and datetime.date.today() > self.expires:
            return False
        return True

    def isAllowed(self, service):
        return service in self.allowed


class ApiKeyStore:
    """ api keys of the key file - the file is reloaded automatically if it has been changed """

    def __init__(self, keyFile, logger, defaultMaxOpenProblems):
        self.__keyFile = keyFile
        self.__logger = logger
        self.__defaultMaxOpenProblems = defaultMaxOpenProblems
        self.__keys = {}
        self.__mtime = None
        self.__lock = threading.Lock()

        if not os.path.isfile(self.__keyFile):
            raise LogLabServerException(f'api key file {self.__keyFile} does not exist - create keys with manageKeys.py or set authentication: False')
        self.__reload()

    def __reload(self):
        mtime = os.path.getmtime(self.__keyFile)
        if mtime == self.__mtime:
            return

        with open(self.__keyFile, 'r', encoding='utf-8') as f:
            entries = yaml.safe_load(f) or []

        keys = {}
        for entry in entries:
            k = ApiKey(entry, self.__defaultMaxOpenProblems)
            keys[k.hash] = k

        self.__keys = keys
        self.__mtime = mtime
        self.__logger.info('auth', f'{len(keys)} api keys loaded from {self.__keyFile}')

    def lookup(self, key):
        """ returns the ApiKey for a key or None """
        with self.__lock:
            try:
                self.__reload()
            except Exception as e:
                # a broken key file must not stop the server - the last valid keys are used
                self.__logger.error('auth', f'cannot reload api key file - {e}')
        return self.__keys.get(hashKey(key))

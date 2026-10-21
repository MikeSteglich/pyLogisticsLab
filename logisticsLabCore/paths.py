""" places of the configuration and the logs of LogisticsLab

    confDir()          LOGLAB_CONF_DIR or <project>/confs  - logisticsLab.yml, logisticsLabServer.yml, apiKeys.yml
    osmConfigFile()    the OSM servers: confs/logisticsLab.local.yml if it exists, otherwise confs/logisticsLab.yml
    logDir()           LOGLAB_LOG_DIR or <project>/logs   - log files, HiGHS.log, matrix cache

    <project> is the directory of the sources (pip install -e .). osm_data uses the same rule for its defaults.
"""

import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def confDir():
    return os.environ.get('LOGLAB_CONF_DIR') or os.path.join(PROJECT_DIR, 'confs')


def confFile(name):
    return os.path.join(confDir(), name)


def osmConfigFile():
    """ a local file (own servers, api keys - not versioned) replaces the servers of the TH Wildau """
    local = confFile('logisticsLab.local.yml')
    return local if os.path.isfile(local) else confFile('logisticsLab.yml')


def logDir():
    return os.environ.get('LOGLAB_LOG_DIR') or os.path.join(PROJECT_DIR, 'logs')


def logFile(name):
    """ file in logDir() - the directory is created """
    os.makedirs(logDir(), exist_ok=True)
    return os.path.join(logDir(), name)

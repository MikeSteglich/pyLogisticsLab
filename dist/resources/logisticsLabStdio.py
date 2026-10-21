""" entry point of the binary logisticsLabStdio (dist/buildStdio.py) - the same as python -m logisticsLabCore.stdio

    bin/logisticsLabStdio finds confs/ next to bin/ (distEnv.py) - an app should pass --logPath.
"""

import multiprocessing

import distEnv
distEnv.setup(__file__)

from logisticsLabCore.stdio import main

if __name__ == '__main__':
    multiprocessing.freeze_support()    # the solver processes (spawn) start this binary again
    main()

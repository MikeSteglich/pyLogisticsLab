""" entry point of the binary logisticsLabStdio (dist/buildStdio.py) - the same as python -m logisticsLabCore.stdio

    bin/logisticsLabStdio finds confs/ next to bin/ (distEnv.py) - an app should pass --logPath.
"""

import multiprocessing
import os
import time

# a solver process (jobs.WorkerSlot): the first step of its start (logisticsLabCore/startTrace.py)
if os.environ.get('LOGLAB_WORKER_TRACE'):
    with open(os.environ['LOGLAB_WORKER_TRACE'], 'a', encoding='utf-8') as _f:
        _f.write(f'{time.strftime("%H:%M:%S")} pid {os.getpid()} - main module of the binary\n')

import distEnv
distEnv.setup(__file__)

from logisticsLabCore.stdio import main

if __name__ == '__main__':
    multiprocessing.freeze_support()    # the solver processes (spawn) start this binary again
    main()

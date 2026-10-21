""" entry point of the binary logisticsLabStdio (dist/buildStdio.py) - the same as python -m logisticsLabCore.stdio """

import multiprocessing

from logisticsLabCore.stdio import main

if __name__ == '__main__':
    multiprocessing.freeze_support()    # the solver processes (spawn) start this binary again
    main()

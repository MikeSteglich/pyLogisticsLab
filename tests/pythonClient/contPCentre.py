""" continuous p-centre in Brandenburg - the same example as tests/dartClient/bin/cont_pcentre.dart

    python contPCentre.py local     starts python -m logisticsLabCore.stdio as child process (JSON-RPC)
    python contPCentre.py remote    REST server LOGLAB_URL (default http://127.0.0.1:8000/v1/) with the key
                                    LOGLAB_API_KEY - from the environment or tests/serverTests/.env (createTestKeys.py)
"""

from logisticsLabClient import LocalBackend, RemoteBackend, LogisticsLabException, loadEnv

import sys


coordinates = [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
               [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]]
demands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8]

problems = {
    'uncapacitated': {"type": "contpcentre", "p": 3, "coordinates": coordinates},
    'capacities 100, 100, 60, single-source': {"type": "contpcentre", "p": 3, "coordinates": coordinates,
                                               "demands": demands, "capacities": [100, 100, 60]},
    'error: p too large': {"type": "contpcentre", "p": 20, "coordinates": coordinates},
}


def createBackend(mode):
    if mode == 'remote':
        env = loadEnv()
        return RemoteBackend(env.get('LOGLAB_URL', 'http://127.0.0.1:8000/v1/'), env.get('LOGLAB_API_KEY', ''))
    # in a desktop app the bundled program is started instead: LocalBackend(command=['./logisticsLabLocal'])
    return LocalBackend()


def evaluate(title, problem, answer):
    """ further processing of the results - as evaluate() in findContPCentreServer.py """
    print(f'== {title}')
    if answer['status'] != 'solution':
        print(f"no solution: {answer['status']} - {answer['message']}\n")
        return

    r = answer['results']
    print(f"largest distance {r['objVal']:.2f} km ({r['solvingTime']} s)")

    capacities = problem.get('capacities')
    for k, (lat, lon) in enumerate(r['locations']):
        customers = [ j for j, a in enumerate(r['assignments']) if a == k ]
        line = f'facility {k} ({lat:.4f}, {lon:.4f}): customers {customers}'
        if capacities is not None:
            load = sum(demands[j] for j in customers)
            cap = capacities[k] if isinstance(capacities, list) else capacities
            line += f', load {load} of {cap}'
        print(line)

    distances = r['customerDistances']
    worst = max(range(len(distances)), key=lambda j: distances[j])
    print(f"farthest customer {worst} {coordinates[worst]}: {distances[worst]:.2f} km "
          f"to facility {r['assignments'][worst]}\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'local'
    with createBackend(mode) as backend:
        for title, problem in problems.items():
            try:
                answer = backend.solve(problem, onStatus=lambda s: print('   ...', s['status']))
                evaluate(f'{mode}: {title}', problem, answer)
            except LogisticsLabException as e:
                # wrong fields (422), unknown key (401/403), too many problems (429) ...
                print(f'== {mode}: {title}\n{e}\n')


if __name__ == '__main__':
    main()

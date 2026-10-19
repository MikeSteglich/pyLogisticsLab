""" command line tool for scenario files (scenario.py) - solves their problems locally or with a server

    python -m logisticsLabCore.cli solve SCENARIO.json [--problem NAME ...] [--out SOLUTIONS.json] [--json] [--quiet]
                                         [--set NAME=VALUE ...] [--server URL --apiKey KEY] [--logPath DIR]
    python -m logisticsLabCore.cli show SCENARIO.json

    solve   solves all problems of the scenario (or the ones given by --problem) and prints the results.
            --out writes the solution documents (logisticsLabSolution) as JSON file, --json prints them as JSON.
            --set overrides a parameter of the problems, e.g. --set p=3 --set maxSolvingTime=30
            Without --server the problems are solved in this process (local core, OSM servers of logisticsLab.yml).
            With --server they are sent to a LogisticsLab server - the key from --apiKey or LOGLAB_API_KEY.
    show    prints a summary of the scenario
"""

from .scenario import Scenario, ScenarioSolver, ScenarioException

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request


#*************** backends ************************************************

class LocalBackend:
    """ the core in this process - the problems are solved in its solver processes """

    def __init__(self, logPath, osmConfig=None):
        from .core import LogisticsLabCore
        from .logger import CoreLogger
        os.makedirs(logPath, exist_ok=True)
        conf = {'maxProblems': 1, 'workDir': logPath, 'tpp': {'solverLogFile': os.path.join(logPath, 'HiGHS.log')}}
        osmConfig = osmConfig or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logisticsLab.yml')
        self.core = LogisticsLabCore(conf, CoreLogger(os.path.join(logPath, 'logisticsLabCli.log')),
                                     osmConfigFile=osmConfig, osmLogFile=os.path.join(logPath, 'logisticsLab.log'))

    def matrix(self, payload):
        from .exception import LogLabCoreException
        try:
            return self.core.geo('matrix', payload)
        except LogLabCoreException as e:
            raise ScenarioException(f'matrix: {e}')

    def solve(self, payload):
        from .exception import LogLabCoreException
        try:
            id = self.core.submit(payload)
        except LogLabCoreException as e:
            raise ScenarioException(str(e))
        except Exception as e:                       # validation errors of the items
            raise ScenarioException(f'wrong problem: {e}')
        while self.core.jobs.get(id).status in ('waiting', 'running'):
            time.sleep(0.1)
        content, _, _ = self.core.fetch(id)
        return content

    def close(self):
        self.core.shutdown()


class RemoteBackend:
    """ a LogisticsLab server (REST) - the results are polled via /v1/results """

    def __init__(self, url, apiKey):
        self.url = url if url.endswith('/') else url + '/'
        self.apiKey = apiKey

    def __post(self, endpoint, body):
        request = urllib.request.Request(self.url + endpoint, data=json.dumps(body).encode('utf-8'), method='POST',
                                         headers={'Content-Type': 'application/json', 'X-API-Key': self.apiKey})
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')
        except urllib.error.URLError as e:
            raise ScenarioException(f'server {self.url} not available: {e.reason}')

    def matrix(self, payload):
        code, answer = self.__post('matrix', payload)
        if code != 200:
            raise ScenarioException(f'matrix: {code} {answer.get("message") or answer.get("detail")}')
        return answer

    def solve(self, payload):
        code, answer = self.__post('solve', payload)
        if code != 200:
            raise ScenarioException(f'{code} {answer.get("message") or answer.get("detail") or answer}')
        while True:
            _, result = self.__post('results', {'id': answer['id']})
            if result.get('status') not in ('waiting', 'running'):
                return result
            time.sleep(0.3)

    def close(self):
        pass


#*************** output ************************************************

def fmt(v):
    if isinstance(v, float):
        return f'{v:,.2f}'.replace(',', ' ') if abs(v) >= 1000 else f'{v:.4g}'
    if isinstance(v, list):
        return '[' + ', '.join(fmt(x) for x in v) + ']'
    return str(v)


def printSolution(solution, out=sys.stdout):
    p = solution['problem']
    print(f"\n== {p['name']} ({p['type']}) - {solution['status']}: {solution['message']}", file=out)
    for w in solution.get('warnings', []):
        print(f'   warning: {w}', file=out)
    r = solution.get('results')
    if not r:
        return
    unit = solution.get('valueUnit')
    print(f"   objective value  {fmt(r['objVal'])}" + (f'   (values in {unit})' if unit else '')
          + f"   {r.get('solvingTime')} s", file=out)
    info = solution.get('matrixInfo')
    if info:
        print(f"   matrix           {info.get('source')}, {info.get('status')}, {info.get('travelmode')}"
              + (f", OSM data {info['osmDate'][:10]}" if info.get('osmDate') else ''), file=out)
    for k, v in (r.get('summary') or {}).items():
        print(f'   {k:16} {fmt(v)}', file=out)
    if r.get('nodes'):
        print('   nodes:', file=out)
        for id, values in r['nodes'].items():
            print(f'      {id:12} ' + ', '.join(f'{k} {fmt(v)}' for k, v in values.items()), file=out)
    if r.get('assignments'):
        print('   assignments:', file=out)
        for a in r['assignments']:
            print(f"      {a['from']:>12} -> {a['to']:12} " + ', '.join(f'{k} {fmt(v)}' for k, v in a.items()
                                                                       if k not in ('from', 'to')), file=out)
    for route in r.get('routes') or []:
        head = f"vehicle {route['vehicle']}: " if 'vehicle' in route else ''
        tail = ', '.join(f'{k} {fmt(route[k])}' for k in ('load', 'distance') if k in route)
        print(f"   route {head}{' -> '.join(route['nodes'])}" + (f'   ({tail})' if tail else ''), file=out)
        if route.get('path') and route['path'] != route['nodes']:
            print(f"      path {' -> '.join(route['path'])}", file=out)
    if r.get('edges'):
        print('   edges:', file=out)
        for e in r['edges']:
            print(f"      {e['from']:>12} -> {e['to']:12} " + ', '.join(f'{k} {fmt(v)}' for k, v in e.items()
                                                                       if k not in ('from', 'to')), file=out)
    if r.get('covering'):
        print('   covering:', file=out)
        for id, sources in r['covering'].items():
            print(f"      {id:12} {', '.join(sources) or '-'}", file=out)


def showScenario(s):
    print(f'{s.id}: {s.name or ""}')
    if s.description:
        print(f'   {s.description}')
    roles = {}
    for n in s.nodes:
        for r in n.roles or ['-']:
            roles[r] = roles.get(r, 0) + 1
    print(f"   nodes      {len(s.nodes)} ({', '.join(f'{k} {v}' for k, v in roles.items())}), "
          f"{sum(not n.active for n in s.nodes)} inactive")
    for name, net in s.networks.items():
        print(f"   network    {name}: {len(net.edges)} edges, {'directed' if net.directed else 'undirected'}")
    for v in s.vehicles:
        print(f'   vehicle    {v.id}: capacity {fmt(v.capacity)}, count {v.count}, depot {v.depot}')
    print(f"   units      {s.units.distance}, {s.units.time} - matrix {s.matrix.matrixSource}, {s.matrix.travelmode}"
          + (f', costPerKm {s.matrix.costPerKm}' if s.matrix.costPerKm else '')
          + (f', costPerHour {s.matrix.costPerHour}' if s.matrix.costPerHour else ''))
    for p in s.problems:
        print(f"   problem    {p.name}: {p.type} {json.dumps(p.parameters, ensure_ascii=False)}"
              + (f' network {p.network} ({p.networkMode})' if p.network else ''))


def parseValue(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


#*************** main ************************************************

def main(argv=None):
    parser = argparse.ArgumentParser(description='solves the problems of LogisticsLab scenario files')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('solve', help='solves the problems of a scenario')
    p.add_argument('scenario')
    p.add_argument('--problem', action='append', help='name of a problem (default: all)')
    p.add_argument('--out', help='file for the solution documents (JSON)')
    p.add_argument('--json', action='store_true', help='print the solution documents as JSON')
    p.add_argument('--quiet', action='store_true', help='no output on the screen')
    p.add_argument('--set', action='append', default=[], metavar='NAME=VALUE', help='parameter of the problems')
    p.add_argument('--server', help='URL of a LogisticsLab server, e.g. http://127.0.0.1:8000/v1/')
    p.add_argument('--apiKey', default=os.environ.get('LOGLAB_API_KEY', ''), help='default: LOGLAB_API_KEY')
    p.add_argument('--osmConfig', help='OSM servers (default: logisticsLabCore/logisticsLab.yml)')
    p.add_argument('--logPath', default=os.path.join(tempfile.gettempdir(), 'logisticsLabCli'))
    p = sub.add_parser('show', help='summary of a scenario')
    p.add_argument('scenario')
    args = parser.parse_args(argv)

    try:
        with open(args.scenario, encoding='utf-8') as f:
            scenario = Scenario.model_validate(json.load(f))
    except Exception as e:
        sys.exit(f'{args.scenario}: {e}')

    if args.command == 'show':
        showScenario(scenario)
        return 0

    problems = [ p for p in scenario.problems if not args.problem or p.name in args.problem ]
    if not problems:
        sys.exit(f'{args.scenario}: no problems' + (f' named {", ".join(args.problem)}' if args.problem else ''))
    overrides = {}
    for s in args.set:
        name, _, value = s.partition('=')
        overrides[name.strip()] = parseValue(value.strip())

    backend = RemoteBackend(args.server, args.apiKey) if args.server else LocalBackend(args.logPath, args.osmConfig)
    solutions, nrOfErrors = [], 0
    try:
        for problem in problems:
            try:
                solution = ScenarioSolver(scenario, backend).solve(problem, overrides)
            except ScenarioException as e:
                solution = {'problem': {'name': problem.name, 'type': problem.type}, 'status': 'error', 'message': str(e)}
            nrOfErrors += solution['status'] not in ('solution', 'noSolution')
            solutions.append(solution)
            if not args.quiet and not args.json:
                printSolution(solution)
    finally:
        backend.close()

    if args.json and not args.quiet:
        print(json.dumps(solutions, indent=2, ensure_ascii=False))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(solutions, f, indent=2, ensure_ascii=False)
    return 1 if nrOfErrors else 0


if __name__ == '__main__':
    sys.exit(main())

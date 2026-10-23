""" command line tool of LogisticsLab - scenario files (logisticsLabCore/scenario.py)

    logisticslab solve SCENARIO.llab [--problem NAME ...] [--out [SOLUTIONS.llsol]] [--json] [--quiet]
                                     [--set NAME=VALUE ...] [--server URL --apiKey KEY] [--logPath DIR]
    logisticslab show SCENARIO.llab
    logisticslab convert OLD.TPPX [-o NEW.llab]
    logisticslab convert --dir SOURCE_DIR --target TARGET_DIR

    (logisticslab is installed by pip install -e . - otherwise python -m logisticsLabCli ...)

    solve   solves all problems of the scenario (or the ones given by --problem) and prints the results.
            --out writes the solution documents (logisticsLabSolution) as JSON file - without a name next to the
            scenario as <name>.llsol, --json prints them as JSON.
            Scenarios are .llab and solutions .llsol files (JSON) - other names are accepted, the field format counts.
            --set overrides a parameter of the problems, e.g. --set p=3 --set maxSolvingTime=30
            Without --server the problems are solved in this process (local core, OSM servers of confs/logisticsLab.yml,
            logs and matrix cache in logs/cli).
            With --server they are sent to a LogisticsLab server - the key from --apiKey or LOGLAB_API_KEY.
    show    prints a summary of the scenario
    convert converts old LogisticsLab files (TPPX, TSPX, CLPX, DLPX, NWFX, VRPX) into scenario files - see logisticsLabCore/convertX.py
"""

from logisticsLabCore import paths
from logisticsLabCore.scenario import Scenario, ScenarioSolver, ScenarioException
from .backends import LocalBackend, RemoteBackend
from logisticsLabCore import convertX

import argparse
import json
import os
import sys
import tempfile


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


SCENARIO_EXTENSIONS = ('.llab', '.json')
SOLUTION_EXTENSION = '.llsol'


def solutionName(scenario):
    """ europa.tppx.llab -> europa.tppx.llsol, next to the scenario """
    for ext in SCENARIO_EXTENSIONS:
        if scenario.lower().endswith(ext):
            return scenario[:-len(ext)] + SOLUTION_EXTENSION
    return scenario + SOLUTION_EXTENSION


def parseValue(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


#*************** convert ************************************************

def convert(args, parser):
    if args.file:
        try:
            target = convertX.convertFile(args.file, args.output)
        except convertX.SkipFile as e:
            sys.exit(f'{args.file}: skipped - {e}')
        print(f'{args.file} -> {target}')
        return 0
    if not args.dir or not args.target:
        parser.error('convert needs a file or --dir and --target')
    converted, skipped, failed = convertX.convertDir(args.dir, args.target)
    print(f'{converted} converted, {len(skipped)} skipped, {len(failed)} failed')
    for line in skipped:
        print(f'   skipped  {line}')
    for line in failed:
        print(f'   FAILED   {line}')
    return 1 if failed else 0


#*************** main ************************************************

def main(argv=None):
    parser = argparse.ArgumentParser(prog='logisticslab', description='LogisticsLab scenario files: solve, show, convert')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('solve', help='solves the problems of a scenario')
    p.add_argument('scenario')
    p.add_argument('--problem', action='append', help='name of a problem (default: all)')
    p.add_argument('--out', nargs='?', const='', help='file for the solution documents - without a name: <scenario>.llsol')
    p.add_argument('--json', action='store_true', help='print the solution documents as JSON')
    p.add_argument('--quiet', action='store_true', help='no output on the screen')
    p.add_argument('--set', action='append', default=[], metavar='NAME=VALUE', help='parameter of the problems')
    p.add_argument('--server', help='URL of a LogisticsLab server, e.g. http://127.0.0.1:8000/v1/')
    p.add_argument('--apiKey', default=os.environ.get('LOGLAB_API_KEY', ''), help='default: LOGLAB_API_KEY')
    p.add_argument('--osmConfig', help='OSM servers (default: confs/logisticsLab.local.yml or confs/logisticsLab.yml)')
    p.add_argument('--logPath', default=os.path.join(paths.logDir(), 'cli'), help='default: logs/cli')
    p = sub.add_parser('show', help='summary of a scenario')
    p.add_argument('scenario')
    p = sub.add_parser('convert', help='converts old LogisticsLab files into scenario files')
    p.add_argument('file', nargs='?', help='an old file, e.g. europa.TPPX')
    p.add_argument('-o', '--output', help='scenario file (default: <name>.<format>.llab next to the old file)')
    p.add_argument('--dir', help='source directory - all X files, the folders are kept')
    p.add_argument('--target', help='target directory for --dir')
    args = parser.parse_args(argv)

    if args.command == 'convert':
        return convert(args, parser)

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
    if args.out is not None:
        args.out = args.out or solutionName(args.scenario)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(solutions, f, indent=2, ensure_ascii=False)
        if not args.quiet:
            print(f'\nsolutions written to {args.out}')
    return 1 if nrOfErrors else 0


if __name__ == '__main__':
    sys.exit(main())

""" converts the old LogisticsLab files (TPPX, TSPX, CLPX, DLPX, NWFX, VRPX) into scenario files (logisticsLabCore/scenario.py)

    logisticslab convert FILE.TPPX [-o FILE.json]
    logisticslab convert --dir SOURCE_DIR --target TARGET_DIR      all X files, the folders are kept

    Only OSM distances and travel times (or bee line) with geographic coordinates are converted - files with own
    matrices (DistFunc OwnDef) or planar coordinates (Map SimpleMap) are skipped. Matrices stored in the files
    (COSTS, DISTANCES, TIMES) are not taken over - the scenario computes them from the coordinates. Exceptions:
    'M' in COSTS (blocked connections) and the sections CAPACITIES and FIXEDCOSTS become a network of connections.
"""

import json
import os
import re

from logisticsLabCore.scenario import Scenario

FORMATS = ('TPPX', 'TSPX', 'CLPX', 'DLPX', 'NWFX', 'VRPX')
SCENARIO_EXTENSION = '.llab'
TABLES = ('SOURCES', 'DESTINATIONS', 'NODES', 'EDGES')
MATRICES = ('COSTS', 'CAPACITIES', 'FIXEDCOSTS', 'DISTANCES', 'TIMES', 'PRENODES')
UNBOUNDED_TIME = 2147483647


class SkipFile(Exception):
    pass


#*************** reader ************************************************

def value(token):
    """ "text" -> text, M -> 'M', numbers -> int or float """
    t = token.strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        return t[1:-1].strip()
    if t == 'M':
        return 'M'
    try:
        f = float(t.replace(',', '.'))
        return int(f) if f.is_integer() and '.' not in t else f
    except ValueError:
        return t


def headerTokens(line):
    """ column names - separated by tabs, sometimes also by several blanks (e.g. 'Country    Volume') """
    names = []
    for t in line.split('\t'):
        names += [ n.strip() for n in re.split(r' {2,}', t.strip()) if n.strip() ]
    return [ n.lstrip('#') for n in names ]


def rowTokens(line, nrOfColumns, where):
    raw = [ t.strip() for t in line.rstrip().split('\t') ]
    while raw and raw[-1] == '':
        raw.pop()
    if any(t.startswith('"') for t in raw):
        # texts are quoted - empty unquoted tokens are only separators
        tokens = [ t for t in raw if t != '' ]
    else:
        # nothing quoted - empty tokens can be empty fields, surplus ones are removed after the coordinates
        tokens = raw
        while len(tokens) > nrOfColumns and '' in tokens[5:]:
            del tokens[5 + tokens[5:].index('')]
    if len(tokens) < nrOfColumns:
        tokens += [''] * (nrOfColumns - len(tokens))        # empty last columns, e.g. Source of CLPX
    if len(tokens) != nrOfColumns:
        raise ValueError(f'{where}: {len(tokens)} values, {nrOfColumns} columns expected')
    return [ value(t) for t in tokens ]


def read(path):
    """ {'type', 'version', 'description', 'options': {name: [values]}, 'tables': {...}, 'matrices': {...}} """
    try:
        text = open(path, encoding='utf-8').read()
    except UnicodeDecodeError:
        text = open(path, encoding='latin-1').read()
    lines = text.splitlines()
    head = lines[0].split('\t')[0].split()
    data = {'type': head[0], 'version': head[1] if len(head) > 1 else '', 'description': '',
            'options': {}, 'tables': {}, 'matrices': {}}
    second = lines[1].strip() if len(lines) > 1 else ''
    if second and not re.fullmatch(r'[A-Z]+', second):
        data['description'] = second.split('\t')[0].strip()

    section, i = None, 1
    while i < len(lines):
        line = lines[i]
        s = line.strip().strip('\t')
        if re.fullmatch(r'[A-Z]+', s.split('\t')[0].strip()) and s.split('\t')[0].strip() in ('OPTIONS', 'EEE') + TABLES + MATRICES:
            section = s.split('\t')[0].strip()
            i += 1
            if section in TABLES:
                # count (the header of the section can be repeated), column names, rows
                while i < len(lines) and lines[i].strip().strip('\t') == section:
                    i += 1
                count = int(float(lines[i].split('\t')[0].strip()))
                columns = headerTokens(lines[i + 1])
                rows = []
                for k in range(count):
                    tokens = rowTokens(lines[i + 2 + k], len(columns), f'{os.path.basename(path)} {section} row {k+1}')
                    rows.append(dict(zip(columns, tokens)))
                data['tables'][section] = rows
                i += 2 + count
            elif section in MATRICES:
                rows = []
                while i < len(lines) and lines[i].strip() and not re.fullmatch(r'[A-Z]+', lines[i].strip()):
                    rows.append([ value(t) for t in lines[i].split('\t') if t.strip() ])
                    i += 1
                data['matrices'][section] = rows
            continue
        if section == 'OPTIONS' and '\t' in line:
            name, *rest = [ t.strip() for t in line.split('\t') ]
            if name:
                data['options'].setdefault(name, []).append(' '.join(t for t in rest if t))
        i += 1
    return data


def option(data, name, default=None):
    v = data['options'].get(name)
    return v[0] if v else default

def isTrue(v):
    return str(v).strip().lower() in ('true', 'y', 'yes', 'j', '1')

def number(v):
    return value(str(v)) if v is not None else None


#*************** nodes ************************************************

class NodeList:
    """ nodes of a scenario - a place that is source and destination (same name and coordinates) is one node """

    def __init__(self):
        self.nodes, self.byId = [], {}

    def add(self, row, roles, idColumn='ID', **attributes):
        id = str(row.get(idColumn) or row.get('Name') or '').strip()
        lat, lon = float(row['y']), float(row['x'])            # x = longitude, y = latitude
        node = self.byId.get(id)
        if node and abs(node['coordinates'][0] - lat) < 1e-6 and abs(node['coordinates'][1] - lon) < 1e-6:
            node['roles'] += [ r for r in roles if r not in node['roles'] ]
            node.update({k: v for k, v in attributes.items() if v is not None})
            return node
        if node:                                                 # same name, other place
            k = 2
            while f'{id}#{k}' in self.byId:
                k += 1
            id = f'{id}#{k}'
        node = {'id': id, 'name': row.get('Name') or id, 'coordinates': [lat, lon], 'roles': list(roles)}
        address = {k: str(row[c]) for k, c in (('street', 'Street'), ('postcode', 'PostCode'), ('city', 'City'),
                                                ('country', 'Country')) if str(row.get(c) or '').strip()}
        if address:
            node['addressDetails'] = address
        node.update({k: v for k, v in attributes.items() if v is not None})
        self.nodes.append(node)
        self.byId[id] = node
        return node

    def idOf(self, name):
        name = str(name).strip()
        if name not in self.byId:
            raise ValueError(f'unknown node {name}')
        return name


def unlimitedOrNumber(v):
    return 'M' if v == 'M' else number(v)


def matrixSettings(data, units):
    """ DistFunc, TravelMode, DistFactor -> matrix options and the matrix kind of the problem """
    distFunc = option(data, 'DistFunc', 'OSM')
    if distFunc == 'OwnDef':
        raise SkipFile('own matrix (DistFunc OwnDef)')
    if option(data, 'Map') == 'SimpleMap':
        raise SkipFile('planar coordinates (Map SimpleMap)')
    matrix = {'travelmode': 'car'}
    # DistFunc decides - OSM/... with TravelMode Bird was computed with road distances
    if distFunc.startswith('GreatCircle') or option(data, 'Distance') == 'GreatCircle':
        matrix.update({'matrixSource': 'beeline', 'detourFactor': 1.0})
    factor = float(number(option(data, 'DistFactor', 1)) or 1)
    if 'TravelTimes' in distFunc:
        kind = 'times' if factor == 1 else 'costs'
        if kind == 'costs':
            matrix['costPerHour'] = factor
    else:
        kind = 'distances' if factor == 1 else 'costs'
        if kind == 'costs':
            matrix['costPerKm'] = factor
    if distFunc in ('OSM/DistancesM', 'GreatCircleM'):
        units['distance'] = 'm'
    return matrix, kind


def scenario(data, id, source, units, matrix, nodes, problems, networks=None, vehicles=None):
    s = {'format': 'logisticsLab', 'version': 1, 'id': id, 'name': data['description'] or id,
         'source': f'{source} ({data["type"]} {data["version"]})', 'units': units, 'matrix': matrix,
         'nodes': nodes.nodes, 'networks': networks or {}, 'vehicles': vehicles or [], 'problems': problems}
    if data['description']:
        s['description'] = data['description']
    return s


#*************** formats ************************************************

def convertTppx(data, id, source):
    units = {'distance': 'km', 'time': 'h'}
    matrix, kind = matrixSettings(data, units)
    nodes = NodeList()
    S = [ nodes.add(r, ['supplier'], supply=unlimitedOrNumber(r.get('Supply')),
                    minSupply=unlimitedOrNumber(r.get('MinSupply')), maxSupply=unlimitedOrNumber(r.get('MaxSupply')))
          for r in data['tables']['SOURCES'] ]
    D = [ nodes.add(r, ['customer'], demand=unlimitedOrNumber(r.get('Demand')),
                    minDemand=unlimitedOrNumber(r.get('MinDemand')), maxDemand=unlimitedOrNumber(r.get('MaxDemand')))
          for r in data['tables']['DESTINATIONS'] ]

    subjectTo = data['options'].get('SubjectTo', [])
    sense = option(data, 'ObjectiveSense', 'MIN').lower()
    if option(data, 'Type') == 'Bottleneck':
        sense = 'minimax'
    par = {'objSense': sense, 'matrixMode': kind}
    for name, flag in (('SupplyRanges', 'useSupplyRanges'), ('DemandRanges', 'useDemandRanges'),
                       ('Capacities', 'useCapacities'), ('SingleSource', 'isSingleSource')):
        if name in subjectTo:
            par[flag] = True
    if option(data, 'KeyFigure') == 'VarAndFixedCosts':
        par['useFixedCosts'] = True
    blocking = option(data, 'Blocking')
    if blocking:
        lo, hi = blocking.split()[:2]
        par['minBlock'], par['maxBlock'] = number(lo), unlimitedOrNumber(hi)

    # connections: blocked pairs ('M' in COSTS), capacities and fixed costs per pair
    costs, caps, fixed = (data['matrices'].get(k) for k in ('COSTS', 'CAPACITIES', 'FIXEDCOSTS'))
    blocked = costs and any(v == 'M' for row in costs for v in row)
    problem = {'name': id, 'type': 'tpp', 'parameters': par}
    networks = {}
    if blocked or caps or fixed:
        edges = []
        for i, s in enumerate(S):
            for j, d in enumerate(D):
                if costs and costs[i][j] == 'M':
                    continue
                e = {'from': s['id'], 'to': d['id']}
                if caps and caps[i][j] != 'M':
                    e['capacity'] = caps[i][j]
                if fixed and fixed[i][j]:
                    e['fixedCost'] = fixed[i][j]
                edges.append(e)
        networks['connections'] = {'directed': True, 'edges': edges}
        problem['network'] = 'connections'
    return scenario(data, id, source, units, matrix, nodes, [problem], networks)


def convertDlpx(data, id, source):
    units = {'distance': 'km', 'time': 'h'}
    matrix, kind = matrixSettings(data, units)
    nodes = NodeList()
    for r in data['tables']['SOURCES']:
        nodes.add(r, ['candidate'], idColumn='Name', fixedCost=number(r.get('FixedCosts')),
                  capacity=unlimitedOrNumber(r.get('Supply')))
    for r in data['tables']['DESTINATIONS']:
        nodes.add(r, ['customer'], idColumn='Name', demand=number(r.get('Demand')))
    type = {'WLP': 'wlp', 'P-Median': 'pmedian', 'P-Centre': 'pcentre', 'Maximal-Covering-Location': 'mcp'}[option(data, 'Type')]
    par = {'matrixMode': kind, 'maxSolvingTime': number(option(data, 'MaxSolvingTime'))}
    if type == 'wlp':
        par['isCapacitated'] = isTrue(option(data, 'Capacitated'))
    elif type in ('pmedian', 'pcentre'):
        par.update({'p': number(option(data, 'NrOfSources')), 'isCapacitated': isTrue(option(data, 'Capacitated')),
                    'isDemandWeighted': isTrue(option(data, 'DemandWeighted'))})
    else:
        par.update({'radius': number(option(data, 'CoveringRadius')), 'maxSrcCost': number(option(data, 'MaxCoveringCosts')),
                    'useFixedCosts': True})
    return scenario(data, id, source, units, matrix, nodes, [{'name': id, 'type': type, 'parameters': par}])


def convertClpx(data, id, source):
    units = {'distance': 'km', 'time': 'h'}
    matrix, _ = matrixSettings(data, units)
    nodes = NodeList()
    # the sources are no nodes - their positions are the result; their number is p, their capacities a parameter
    # (fixed sources and customers fixed to a source are not supported by the continuous problems)
    sources = data['tables']['SOURCES']
    for r in data['tables']['DESTINATIONS']:
        nodes.add(r, ['customer'], idColumn='Name', demand=number(r.get('Demand')),
                  costFactor=number(r.get('CostFactor')) if r.get('CostFactor') not in (None, '', 1, 1.0) else None)
    type = {'P-Median': 'contpmedian', 'P-Centre': 'contpcentre'}[option(data, 'Type')]
    par = {'p': len(sources), 'isCapacitated': isTrue(option(data, 'Capacitated')),
           'isDemandWeighted': isTrue(option(data, 'DemandWeighted'))}
    if par['isCapacitated']:
        caps = [ unlimitedOrNumber(r.get('Capacity')) for r in sources ]
        par['capacities'] = caps[0] if len(set(caps)) == 1 else caps
    return scenario(data, id, source, units, matrix, nodes, [{'name': id, 'type': type, 'parameters': par}])


def convertNwfx(data, id, source):
    units = {'distance': 'km', 'time': 'h'}
    matrix, kind = matrixSettings(data, units)
    nodes = NodeList()
    for r in data['tables']['NODES']:
        volume = number(r.get('Volume')) or 0
        roles = ['supplier'] if volume > 0 else ['customer'] if volume < 0 else ['transit']
        maxCap = unlimitedOrNumber(r.get('MaxCap'))
        nodes.add(r, roles, supply=volume if volume > 0 else None, demand=-volume if volume < 0 else None,
                  minCap=number(r.get('MinCap')) or None,
                  maxCap=None if maxCap in ('M', 0, None) else maxCap)
    edges = []
    for r in data['tables']['EDGES']:
        e = {'from': nodes.idOf(r['From']), 'to': nodes.idOf(r['To'])}
        if unlimitedOrNumber(r.get('MaxCap')) not in ('M', None):
            e['capacity'] = unlimitedOrNumber(r['MaxCap'])
        if number(r.get('MinCap')):
            e['minFlow'] = number(r['MinCap'])
        edges.append(e)
    problem = {'name': id, 'type': 'mincostflow', 'parameters': {'matrixMode': kind}, 'network': 'network'}
    return scenario(data, id, source, units, matrix, nodes, [problem], {'network': {'directed': True, 'edges': edges}})


def convertTspx(data, id, source):
    units = {'distance': 'km', 'time': 'h'}
    matrix, kind = matrixSettings(data, units)
    nodes = NodeList()
    for r in data['tables']['NODES']:
        node = nodes.add(r, [])
        if str(r.get('Active', 'Y')).strip().upper() in ('N', 'NO', 'FALSE'):
            node['active'] = False
    edges = [ {'from': nodes.idOf(r['From']), 'to': nodes.idOf(r['To']),
               **({'directed': True} if str(r.get('Type', 'U')).strip().upper() == 'D' else {})}
              for r in data['tables'].get('EDGES', []) ]
    ptype = option(data, 'ProblemType', 'Tsp')
    start, dest = option(data, 'StartNode'), option(data, 'DestNode')
    par = {'matrixMode': kind}
    networks = {'network': {'directed': False, 'edges': edges}} if edges else {}
    if ptype == 'Cpp':
        if not edges:
            raise SkipFile('Cpp without edges')
        problem = {'name': id, 'type': 'cpp', 'parameters': {**par, 'startNode': start}, 'network': 'network'}
    else:
        par['startNode'] = None if start in (None, '_Open') else start
        par['endNode'] = None if dest in (None, '_Open') else dest
        if ptype == 'OpenTsp' and par['endNode'] == par['startNode'] and par['startNode'] is not None:
            par['endNode'] = None
        problem = {'name': id, 'type': 'tsp', 'parameters': par}
        # edges: the route uses the shortest paths of the network, entireNetwork: the complete OSM matrix
        if option(data, 'DistMatrixMode') == 'edges' and edges:
            problem.update({'network': 'network', 'networkMode': 'shortestPaths'})
    return scenario(data, id, source, units, matrix, nodes, [problem], networks)


def convertVrpx(data, id, source):
    units = {'distance': 'km', 'time': 'min'}
    matrix, _ = matrixSettings(data, units)
    if number(option(data, 'AvgVehicleSpeed')):
        matrix['averageSpeed'] = number(option(data, 'AvgVehicleSpeed'))
    depot = str(option(data, 'Depot')).strip().strip('"')
    nodes = NodeList()
    for r in data['tables']['NODES']:
        isDepot = str(r['ID']).strip() == depot
        end = number(r.get('End TW'))
        tw = [number(r.get('Start TW')) or 0, None if end is None or end >= UNBOUNDED_TIME else end]
        nodes.add(r, ['depot'] if isDepot else ['customer'], demand=None if isDepot else number(r.get('Demand')),
                  serviceTime=number(r.get('Service time')) or None,
                  timeWindow=tw if (tw[0] or tw[1] is not None) else None)
    nrOfCustomers = len(data['tables']['NODES']) - 1
    vehicles = [{'id': 'V', 'capacity': number(option(data, 'Capacity')), 'count': nrOfCustomers, 'depot': depot}]
    par = {'useTimeWindows': isTrue(option(data, 'WithTimeWindows')), 'maxSolvingTime': number(option(data, 'MaxSolvingTime'))}
    if isTrue(option(data, 'WithMaxTime')):
        h, m = str(option(data, 'MaxTime')).split(':')
        par['maxTime'] = int(h) * 60 + int(m)
    if isTrue(option(data, 'WithMaxLength')):
        par['maxDist'] = number(option(data, 'MaxLength'))
    return scenario(data, id, source, units, matrix, nodes, [{'name': id, 'type': 'vrp', 'parameters': par}],
                    vehicles=vehicles)


CONVERTERS = {'TPPX': convertTppx, 'DLPX': convertDlpx, 'CLPX': convertClpx, 'NWFX': convertNwfx,
              'TSPX': convertTspx, 'VRPX': convertVrpx}


def convert(path, source=None):
    """ scenario dict of an X file - raises SkipFile for files that are not converted """
    ext = path.rsplit('.', 1)[-1].upper()
    data = read(path)
    stem = os.path.basename(path).rsplit('.', 1)[0]
    s = CONVERTERS[ext](data, stem, source or os.path.basename(path))
    Scenario.model_validate(s)                       # the result must be a valid scenario
    return s


def targetName(path):
    """ drogma.CLPX -> drogma.clpx.llab - the same name exists for several formats """
    stem, ext = os.path.basename(path).rsplit('.', 1)
    return f'{stem}.{ext.lower()}{SCENARIO_EXTENSION}'


def write(s, target):
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
        f.write('\n')


def convertFile(path, output=None):
    """ converts one file - returns the scenario file, raises SkipFile for files that are not converted """
    s = convert(path)
    target = output or os.path.join(os.path.dirname(path), targetName(path))
    write(s, target)
    return target


def convertDir(source, target):
    """ converts all X files of source into target, the folders are kept - (converted, skipped, failed) """
    converted, skipped, failed = 0, [], []
    for root, _, files in os.walk(source):
        for fn in sorted(files):
            if fn.rsplit('.', 1)[-1] not in FORMATS:
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, source)
            try:
                s = convert(path, source=rel)
                write(s, os.path.join(target, os.path.dirname(rel), targetName(fn)))
                converted += 1
            except SkipFile as e:
                skipped.append(f'{rel}: {e}')
            except Exception as e:
                failed.append(f'{rel}: {type(e).__name__} {e}')
    return converted, skipped, failed

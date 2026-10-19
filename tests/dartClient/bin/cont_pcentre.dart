// Continuous p-centre in Brandenburg - the same example as tests/serverTests/findContPCentreServer.py
//
//   dart run bin/cont_pcentre.dart local      starts python -m logisticsLabCore.stdio as child process
//                                             (python: LOGLAB_PYTHON, default python3)
//   dart run bin/cont_pcentre.dart remote     REST server LOGLAB_URL (default http://127.0.0.1:8000/v1/)
//                                             with the api key LOGLAB_API_KEY - from the environment or from
//                                             tests/serverTests/.env (python createTestKeys.py)

import 'dart:io';

import 'package:logisticslab_client/logisticslab_client.dart';

const coordinates = [
  [52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
  [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06],
];
const demands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8];

/// environment variables, completed by KEY=VALUE lines of tests/serverTests/.env
Map<String, String> loadEnv() {
  final env = Map.of(Platform.environment);
  final file = File('${Directory.current.parent.path}/serverTests/.env');
  if (file.existsSync()) {
    for (final line in file.readAsLinesSync()) {
      final i = line.indexOf('=');
      if (line.trim().startsWith('#') || i < 0) continue;
      env.putIfAbsent(line.substring(0, i).trim(), () => line.substring(i + 1).trim());
    }
  }
  return env;
}

LogisticsLabBackend createBackend(String mode) {
  final env = loadEnv();
  if (mode == 'remote') {
    return RemoteBackend(Uri.parse(env['LOGLAB_URL'] ?? 'http://127.0.0.1:8000/v1/'), env['LOGLAB_API_KEY'] ?? '');
  }
  // python with pip install -e . of the project - in the app the bundled program is started instead
  return LocalBackend(
    env['LOGLAB_PYTHON'] ?? 'python3',
    ['-m', 'logisticsLabCore.stdio', '--logPath', '${Directory.systemTemp.path}/logisticsLabDart'],
  );
}

/// example of further processing - as evaluate() in findContPCentreServer.py
void evaluate(String title, Map<String, dynamic> problem, ProblemAnswer answer) {
  print('== $title');
  if (!answer.isSolution) {
    print('no solution: ${answer.status} - ${answer.message}\n');
    return;
  }
  final r = ContLocationResults.fromJson(answer.results!);
  print('largest distance ${r.objVal.toStringAsFixed(2)} km (${r.solvingTime} s)');

  final capacities = problem['capacities'];
  for (var k = 0; k < r.locations.length; k++) {
    final loc = r.locations[k];
    final customers = r.customersOf(k);
    var line = 'facility $k (${loc.lat.toStringAsFixed(4)}, ${loc.lon.toStringAsFixed(4)}): customers $customers';
    if (capacities != null) {
      final load = customers.fold<num>(0, (sum, j) => sum + demands[j]);
      final cap = capacities is List ? capacities[k] : capacities;
      line += ', load $load of $cap';
    }
    print(line);
  }

  var worst = 0;
  for (var j = 1; j < r.customerDistances.length; j++) {
    if (r.customerDistances[j] > r.customerDistances[worst]) worst = j;
  }
  print('farthest customer $worst ${coordinates[worst]}: ${r.customerDistances[worst].toStringAsFixed(2)} km '
      'to facility ${r.assignments[worst]}\n');
}

Future<void> main(List<String> args) async {
  final mode = args.isEmpty ? 'local' : args.first;
  final backend = createBackend(mode);
  await backend.start();

  final problems = {
    'uncapacitated': {'type': 'contpcentre', 'p': 3, 'coordinates': coordinates},
    'capacities 100, 100, 60, single-source': {
      'type': 'contpcentre', 'p': 3, 'coordinates': coordinates, 'demands': demands, 'capacities': [100, 100, 60],
    },
    'error: p too large': {'type': 'contpcentre', 'p': 20, 'coordinates': coordinates},
  };

  try {
    for (final MapEntry(key: title, value: problem) in problems.entries) {
      try {
        final answer = await backend.solve(problem, onStatus: (s) => print('   ... ${s.status}'));
        evaluate('$mode: $title', problem, answer);
      } on LogisticsLabException catch (e) {
        // the local interface reports wrong problems as JSON-RPC error, the server as answer with status error
        print('== $mode: $title\n$e\n');
      }
    }
  } finally {
    await backend.close();
  }
}

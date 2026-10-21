// Vehicle routing with time windows - schedule of every route (arrival, waiting, service, travel times)
//
//   dart run bin/vrp.dart local      starts python -m logisticsLabCore.stdio as child process
//                                    (python: LOGLAB_PYTHON, default python3)
//   dart run bin/vrp.dart remote     REST server LOGLAB_URL with the api key LOGLAB_API_KEY (see cont_pcentre.dart)
//
// The times come from the server - the app needs no time matrix. With coordinates instead of distances and
// times the server loads both from the OSM servers (times in seconds, distances in meters).

import 'cont_pcentre.dart' show createBackend;
import 'package:logisticslab_client/logisticslab_client.dart';

// node 0 is the depot - distances in km, times in minutes
const distances = [
  [0, 10, 20, 15, 12],
  [10, 0, 12, 9, 18],
  [20, 12, 0, 7, 25],
  [15, 9, 7, 0, 14],
  [12, 18, 25, 14, 0],
];
const times = distances;
const demands = [0, 3, 4, 5, 6];
const serviceTimes = [0, 5, 5, 5, 5];
const timeWindows = [
  [0, 480], [0, 480], [60, 120], [0, 480], [30, 90],
];

String fmt(double? v) => v == null ? '-' : v.toStringAsFixed(1).padLeft(6);

void printSchedule(VrpResults r) {
  for (final k in r.usedVehicles) {
    final t = r.totals(k);
    print('vehicle $k: distance ${t.distance}, load ${t.load}, travel ${t.travelTime}, waiting ${t.waitingTime}, '
        'service ${t.serviceTime}, duration ${t.duration}');
    print('   node  arrival  waiting   start  service  departure  travel  distance');
    for (final s in r.stops(k)) {
      print('   ${s.node.toString().padLeft(4)}   ${fmt(s.arrival)}   ${fmt(s.waitingTime)}  ${fmt(s.start)}   '
          '${fmt(s.serviceTime)}     ${fmt(s.departure)}  ${fmt(s.travelTime)}    ${fmt(s.distance)}');
    }
  }
}

Future<void> main(List<String> args) async {
  final mode = args.isEmpty ? 'local' : args.first;
  final backend = createBackend(mode);
  await backend.start();
  try {
    final problem = {
      'type': 'vrp', 'distances': distances, 'times': times, 'demands': demands, 'capacities': [10, 10],
      'serviceTimes': serviceTimes, 'timeWindows': timeWindows, 'maxWaitingTime': 60, 'maxSolvingTime': 2,
    };
    final answer = await backend.solve(problem, onStatus: (s) => print('   ... ${s.status}'));
    if (!answer.isSolution) {
      print('no solution: ${answer.status} - ${answer.message}');
      return;
    }
    final r = VrpResults.fromJson(answer.results!);
    print('== $mode: total distance ${r.objVal} (${r.solvingTime} s)');
    printSchedule(r);
  } on LogisticsLabException catch (e) {
    print('== $mode\n$e');
  } finally {
    await backend.close();
  }
}

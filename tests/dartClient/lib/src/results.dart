/// Typed answers - the same structure as logisticsLabCore/results.py (python -m logisticsLabCore.schema).
/// Indices are 0-based positions of the input, -1 means none. JSON numbers are read as num.
library;

double _d(dynamic v) => (v as num).toDouble();
List<double> _vector(dynamic v) => (v as List).map(_d).toList();
List<List<double>> _matrix(dynamic v) => (v as List).map(_vector).toList();
List<int> _ints(dynamic v) => (v as List).map((e) => (e as num).toInt()).toList();

/// Answer of /v1/results and of the stdio methods solve, status, result and cancel.
class ProblemAnswer {
  final String id;
  final String status;       // waiting, running, solution, noSolution, error, cancelled
  final String message;
  final Map<String, dynamic>? results;   // only with status solution - fields depend on the problem type

  ProblemAnswer(this.id, this.status, this.message, this.results);

  factory ProblemAnswer.fromJson(Map<String, dynamic> json) =>
      ProblemAnswer(json['id'] as String, json['status'] as String, json['message'] as String? ?? '',
          json['results'] as Map<String, dynamic>?);

  bool get isSolution => status == 'solution' && results != null;
}

/// Fields of all results.
class ResultFields {
  final double objVal;
  final double solvingTime;
  ResultFields.fromJson(Map<String, dynamic> json)
      : objVal = _d(json['objVal']),
        solvingTime = _d(json['solvingTime']);
}

/// Results of contpmedian and contpcentre (ContLocationResults).
class ContLocationResults extends ResultFields {
  final List<({double lat, double lon})> locations;
  final List<int> assignments;
  final List<double> customerDistances;
  final List<List<double>>? flows;      // [facilities x customers], only with isSingleSource false

  ContLocationResults.fromJson(super.json)
      : locations = (json['locations'] as List).map((l) => (lat: _d(l[0]), lon: _d(l[1]))).toList(),
        assignments = _ints(json['assignments']),
        customerDistances = _vector(json['customerDistances']),
        flows = json['flows'] == null ? null : _matrix(json['flows']),
        super.fromJson();

  /// customers of facility k
  List<int> customersOf(int k) => [for (var j = 0; j < assignments.length; j++) if (assignments[j] == k) j];
}

/// Results of mincostflow and maxflow (FlowResults).
class FlowResults extends ResultFields {
  final List<double> flows;
  FlowResults.fromJson(super.json)
      : flows = _vector(json['flows']),
        super.fromJson();
}

List<List<double>>? _optMatrix(dynamic v) => v == null ? null : _matrix(v);

/// One stop of a vrp route - times in the unit of the time matrix (from coordinates: seconds),
/// null without times.
class VrpStop {
  final int node;              // index of the input, the depot at the start and at the end
  final double? arrival;
  final double? waitingTime;   // before the service, because of a time window
  final double? start;         // start of the service = arrival + waitingTime
  final double? serviceTime;
  final double? travelTime;    // from the previous stop, 0 at the start
  final double load;           // demand delivered at this stop
  final double distance;       // distance driven up to this stop

  VrpStop(this.node, this.arrival, this.waitingTime, this.start, this.serviceTime, this.travelTime, this.load,
      this.distance);

  double? get departure => start == null ? null : start! + (serviceTime ?? 0);
}

/// Totals of a vrp route.
typedef VrpRouteTotals = ({double distance, double load, double? travelTime, double? waitingTime,
    double? serviceTime, double? duration});

/// Results of vrp (VrpResults) - lists per route (vehicle) and per stop of the route.
/// The schedule (arrivals ... serviceTimes) is calculated by the server from its time matrix - with times or
/// coordinates in the request. Without time windows and maxTime every route starts at 0 and nothing waits.
class VrpResults extends ResultFields {
  final List<List<int>> routes;                 // node sequence of every vehicle, [depot, depot] if unused
  final List<List<double>> routeLoads;          // demand delivered at every stop
  final List<List<double>> routeDistances;      // distance driven up to every stop (0 at the start)
  final List<List<double>>? routeTimes;         // start of the service
  final List<List<double>>? routeArrivals;
  final List<List<double>>? routeTravelTimes;   // from the previous stop
  final List<List<double>>? routeWaitingTimes;
  final List<List<double>>? routeServiceTimes;
  final List<List<double>>? distances;          // matrices calculated from the coordinates
  final List<List<double>>? times;

  VrpResults.fromJson(super.json)
      : routes = (json['routes'] as List).map(_ints).toList(),
        routeLoads = _matrix(json['routeLoads']),
        routeDistances = _matrix(json['routeDistances']),
        routeTimes = _optMatrix(json['routeTimes']),
        routeArrivals = _optMatrix(json['routeArrivals']),
        routeTravelTimes = _optMatrix(json['routeTravelTimes']),
        routeWaitingTimes = _optMatrix(json['routeWaitingTimes']),
        routeServiceTimes = _optMatrix(json['routeServiceTimes']),
        distances = _optMatrix(json['distances']),
        times = _optMatrix(json['times']),
        super.fromJson();

  /// vehicles with at least one customer
  List<int> get usedVehicles => [for (var k = 0; k < routes.length; k++) if (routes[k].length > 2) k];

  /// the stops of the route of vehicle k
  List<VrpStop> stops(int k) {
    double? at(List<List<double>>? m, int i) => m == null ? null : m[k][i];
    return [
      for (var i = 0; i < routes[k].length; i++)
        VrpStop(routes[k][i], at(routeArrivals, i), at(routeWaitingTimes, i), at(routeTimes, i),
            at(routeServiceTimes, i), at(routeTravelTimes, i), routeLoads[k][i], routeDistances[k][i]),
    ];
  }

  /// totals of the route of vehicle k - duration from the start at the depot to the return
  VrpRouteTotals totals(int k) {
    double? sum(List<List<double>>? m) => m?[k].fold<double>(0, (s, v) => s + v);
    return (
      distance: routeDistances[k].last,
      load: routeLoads[k].fold<double>(0, (s, v) => s + v),
      travelTime: sum(routeTravelTimes),
      waitingTime: sum(routeWaitingTimes),
      serviceTime: sum(routeServiceTimes),
      duration: routeTimes == null ? null : routeTimes![k].last - routeTimes![k].first,
    );
  }
}

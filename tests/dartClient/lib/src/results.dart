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

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'results.dart';

/// Error of a request - httpStatus is the same for both backends (400, 403, 404, 422, 429, 500 ...).
class LogisticsLabException implements Exception {
  final int httpStatus;
  final String message;
  LogisticsLabException(this.httpStatus, this.message);

  @override
  String toString() => 'LogisticsLabException($httpStatus): $message';
}

/// Status change of a problem, e.g. to show the progress in the UI.
typedef StatusCallback = void Function(ProblemAnswer status);

const finishedStatus = ['solution', 'noSolution', 'error', 'cancelled'];

/// Common interface of the app - the rest of the app does not know whether it computes locally or remotely.
abstract class LogisticsLabBackend {
  Future<void> start();

  /// Submits a problem ({type: ..., ...} as for /v1/solve) and waits for its answer.
  /// The answer has status solution (with results), noSolution, error or cancelled.
  Future<ProblemAnswer> solve(Map<String, dynamic> problem, {StatusCallback? onStatus});

  Future<ProblemAnswer> cancel(String id);

  Future<void> close();
}

//*************** local: child process with JSON-RPC 2.0 over stdin/stdout ************************************

/// Starts the local interface (python -m logisticsLabCore.stdio or the bundled program) as child process.
class LocalBackend implements LogisticsLabBackend {
  final String executable;
  final List<String> arguments;
  final String? workingDirectory;
  final Map<String, String>? environment;

  late final Process _process;
  int _nextId = 1;
  final _pending = <int, Completer<dynamic>>{};
  final _ready = Completer<void>();
  final _done = <String, Completer<void>>{};         // problem id -> finished
  final _finished = <String>{};                      // finished before solve() waits for them
  final _onStatus = <String, StatusCallback>{};

  LocalBackend(this.executable, this.arguments, {this.workingDirectory, this.environment});

  @override
  Future<void> start() async {
    _process = await Process.start(executable, arguments,
        workingDirectory: workingDirectory, environment: environment);
    // stderr: log output of the core, CMPL and HiGHS - stdout belongs to the protocol only
    _process.stderr.transform(utf8.decoder).listen((_) {});
    _process.stdout.transform(utf8.decoder).transform(const LineSplitter()).listen(_onLine,
        onDone: () => _failAll(LogisticsLabException(500, 'local process has stopped')));
    await _ready.future.timeout(const Duration(seconds: 60));
  }

  void _onLine(String line) {
    final Map<String, dynamic> msg = jsonDecode(line);
    if (msg.containsKey('id') && msg['id'] != null) {
      // answer to a request
      final completer = _pending.remove(msg['id']);
      if (msg.containsKey('error')) {
        final e = msg['error'];
        final data = e['data'];
        final status = data is Map && data['httpStatus'] is int ? data['httpStatus'] as int : 500;
        completer?.completeError(LogisticsLabException(status, '${e['message']}'));
      } else {
        completer?.complete(msg['result']);
      }
    } else if (msg['method'] == 'ready') {
      if (!_ready.isCompleted) _ready.complete();
    } else if (msg['method'] == 'jobStatus') {
      final status = ProblemAnswer.fromJson(msg['params']);
      _onStatus[status.id]?.call(status);
      if (finishedStatus.contains(status.status)) {
        _finished.add(status.id);
        _done[status.id]?.complete();
      }
    }
  }

  void _failAll(Object error) {
    for (final c in _pending.values) {
      c.completeError(error);
    }
    _pending.clear();
  }

  Future<dynamic> _call(String method, Map<String, dynamic> params) {
    final id = _nextId++;
    final completer = Completer<dynamic>();
    _pending[id] = completer;
    _process.stdin.writeln(jsonEncode({'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params}));
    return completer.future;
  }

  @override
  Future<ProblemAnswer> solve(Map<String, dynamic> problem, {StatusCallback? onStatus}) async {
    final job = ProblemAnswer.fromJson(await _call('solve', problem));
    if (onStatus != null) _onStatus[job.id] = onStatus;
    // the notification can arrive before the answer of solve
    if (!_finished.contains(job.id)) {
      final done = _done[job.id] = Completer<void>();
      await done.future;
    }
    _done.remove(job.id);
    _finished.remove(job.id);
    _onStatus.remove(job.id);
    return ProblemAnswer.fromJson(await _call('result', {'id': job.id}));
  }

  @override
  Future<ProblemAnswer> cancel(String id) async => ProblemAnswer.fromJson(await _call('cancel', {'id': id}));

  @override
  Future<void> close() async {
    try {
      await _call('shutdown', {}).timeout(const Duration(seconds: 5));
    } catch (_) {}
    await _process.stdin.close();
    await _process.exitCode.timeout(const Duration(seconds: 10), onTimeout: () {
      _process.kill();
      return -1;
    });
  }
}

//*************** remote: REST server with api key ************************************

class RemoteBackend implements LogisticsLabBackend {
  final Uri baseUrl;               // e.g. http://127.0.0.1:8000/v1/
  final String apiKey;
  final Duration pollInterval;
  final _client = HttpClient();

  RemoteBackend(this.baseUrl, this.apiKey, {this.pollInterval = const Duration(milliseconds: 300)});

  @override
  Future<void> start() async {}

  Future<(int, Map<String, dynamic>)> _post(String endpoint, Map<String, dynamic> body) async {
    final request = await _client.postUrl(baseUrl.resolve(endpoint));
    request.headers.contentType = ContentType.json;
    request.headers.set('X-API-Key', apiKey);
    request.write(jsonEncode(body));
    final response = await request.close();
    final text = await response.transform(utf8.decoder).join();
    return (response.statusCode, jsonDecode(text) as Map<String, dynamic>);
  }

  @override
  Future<ProblemAnswer> solve(Map<String, dynamic> problem, {StatusCallback? onStatus}) async {
    final (code, body) = await _post('solve', problem);
    if (code != 200) {
      // rejected: 401/403 api key, 422 wrong fields, 429 too many problems, ...
      throw LogisticsLabException(code, '${body['message'] ?? body['detail'] ?? body}');
    }
    final id = body['id'] as String;
    String? lastStatus;
    while (true) {
      // /results answers 200 for solution, 404 for noSolution, 400 or 500 for error - the body is always the answer
      final (_, answerJson) = await _post('results', {'id': id});
      final answer = ProblemAnswer.fromJson(answerJson);
      if (answer.status != lastStatus) {
        lastStatus = answer.status;
        onStatus?.call(answer);
      }
      if (finishedStatus.contains(answer.status)) return answer;
      await Future.delayed(pollInterval);
    }
  }

  @override
  Future<ProblemAnswer> cancel(String id) async => ProblemAnswer.fromJson((await _post('cancel', {'id': id})).$2);

  @override
  Future<void> close() async => _client.close();
}

/// Checks the language files: every message key of the modules is in every language, no language has keys that the
/// others do not have. dart run bin/i18n_check.dart [i18n directory]
library;

import 'dart:io';

import 'package:logisticslab_client/logisticslab_client.dart';

void main(List<String> args) {
  final dir = args.isNotEmpty ? args[0] : 'i18n';
  final used = allMessageKeys();
  final langs = {for (final l in supportedLanguages) l: Strings.load(dir, l)};
  final all = {for (final s in langs.values) ...s.keys};
  var errors = 0;
  for (final MapEntry(key: lang, value: s) in langs.entries) {
    // .help texts are optional
    final missing = {...used.where((k) => !k.endsWith('.help')), ...all}.difference(s.keys);
    for (final k in missing.toList()..sort()) {
      print('$lang: missing $k');
      errors++;
    }
  }
  final unused = all.difference(used).where((k) => !k.endsWith('.help') && !k.startsWith('hint.'));
  for (final k in unused) {
    print('not used by a module: $k');
  }

  // example: the same check in both languages
  for (final s in langs.values) {
    final p = tppSpec.defaultParameters()..['mipGap'] = -1;
    print('${s.language}: ${s(tppSpec.label)} - ${tppSpec.validateParameters(p).map(s.message).join('; ')}');
  }
  exit(errors == 0 ? 0 : 1);
}

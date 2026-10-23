/// Texts of the UI in the chosen language - sketch.
///
/// One flat JSON file per language (i18n/de.json, i18n/en.json) with message keys as in modules.dart.
/// Placeholders {name} are replaced by the arguments; an argument that is itself a message key (e.g. {label})
/// is translated first. Missing texts come from the fallback language, at last the key itself is shown.
/// Numbers and dates are formatted by the app with the locale (in Flutter package intl), not here.
library;

import 'dart:convert';
import 'dart:io';

import 'modules.dart';

const supportedLanguages = ['de', 'en'];

class Strings {
  final String language;
  final Map<String, String> _texts;
  final Strings? fallback;

  Strings(this.language, this._texts, {this.fallback});

  /// Reads i18n/<language>.json from dir - English is the fallback of the other languages.
  static Strings load(String dir, String language) {
    Map<String, String> read(String lang) =>
        (jsonDecode(File('$dir/$lang.json').readAsStringSync()) as Map<String, dynamic>).cast<String, String>();
    final en = Strings('en', read('en'));
    return language == 'en' ? en : Strings(language, read(language), fallback: en);
  }

  bool has(String key) => _texts.containsKey(key);

  Set<String> get keys => _texts.keys.toSet();

  String call(String key, [Map<String, Object> args = const {}]) {
    var text = _texts[key] ?? fallback?.call(key) ?? key;
    args.forEach((name, value) {
      final v = value is String && (has(value) || (fallback?.has(value) ?? false)) ? call(value) : '$value';
      text = text.replaceAll('{$name}', v);
    });
    return text;
  }

  String message(Message m) => call(m.key, m.args);
}

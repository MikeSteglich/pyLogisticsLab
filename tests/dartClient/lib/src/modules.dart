/// Description of the problem types for a common UI - sketch.
///
/// The UI does not have its own screen per problem type. It builds the node mask, the parameter form, the edge mask
/// and the result tables from a ModuleSpec. The keys are the names of the llab format (docs/dateiformate.md):
/// node attributes, problem parameters and the result fields of the llsol file.
///
/// A ModuleSpec contains no texts, only message keys - the texts are in i18n/<language>.json (see strings.dart):
///   module.<type>, module.<type>.description    label and description of the problem type
///   group.<group>                               group of the problem chooser
///   role.<node role>                            e.g. role.supplier
///   field.<key>, field.<key>.help               fields of the masks - labelKey overrides field.<key>
///   choice.<field key>.<value>                  values of a choice field
///   result.<key>                                columns of the result tables
///   error.<kind>                                messages of the checks with {label}, {min}, {value}
library;

enum ModuleGroup { transport, location, routing, network }

enum FieldKind {
  number,
  unlimited,        // number or 'M' (no limit) - shown as empty field with the hint "unlimited"
  integer,
  boolean,
  choice,
  text,
}

/// Text to be shown in the language of the UI - key with arguments, e.g. error.min with {label} and {min}.
class Message {
  final String key;
  final Map<String, Object> args;
  const Message(this.key, [this.args = const {}]);

  @override
  String toString() => args.isEmpty ? key : '$key $args';
}

/// Visibility of a field depending on the current parameters of the problem, e.g. minSupply only with useSupplyRanges.
typedef FieldCondition = bool Function(Map<String, dynamic> parameters);

class FieldSpec {
  final String key;
  final FieldKind kind;
  final String? labelKey;            // default field.<key>
  final String? unit;
  final Object? defaultValue;
  final List<String> choices;        // values of FieldKind.choice - labels choice.<key>.<value>
  final bool required;
  final num? min;
  final FieldCondition? visibleIf;

  const FieldSpec(this.key, this.kind,
      {this.labelKey, this.unit, this.defaultValue, this.choices = const [], this.required = false, this.min,
      this.visibleIf});

  String get label => labelKey ?? 'field.$key';
  String get help => '$label.help';
  String choiceLabel(String value) => 'choice.$key.$value';

  bool isVisible(Map<String, dynamic> parameters) => visibleIf?.call(parameters) ?? true;

  /// Message for a wrong value or null - the server checks again, this is only for the mask.
  /// The argument label is the message key of the field, the UI replaces it by its text.
  Message? validate(Object? value) {
    if (value == null || value == '') return required ? Message('error.required', {'label': label}) : null;
    switch (kind) {
      case FieldKind.number || FieldKind.integer || FieldKind.unlimited:
        if (kind == FieldKind.unlimited && value == 'M') return null;
        if (value is! num) return Message('error.number', {'label': label});
        if (kind == FieldKind.integer && value != value.roundToDouble()) return Message('error.integer', {'label': label});
        if (min != null && value < min!) return Message('error.min', {'label': label, 'min': min!});
        return null;
      case FieldKind.boolean:
        return value is bool ? null : Message('error.boolean', {'label': label});
      case FieldKind.choice:
        return choices.contains(value) ? null : Message('error.choice', {'label': label, 'value': value});
      case FieldKind.text:
        return value is String ? null : Message('error.text', {'label': label});
    }
  }

  Iterable<String> get messageKeys => [label, for (final c in choices) choiceLabel(c)];
}

/// Role of the nodes in a problem, e.g. sources of a tpp. The problem parameter roles can map it to another node role.
class RoleSpec {
  final String key;                  // key in parameters.roles, e.g. sources
  final String defaultRole;          // node role, e.g. supplier - label role.<defaultRole>
  final List<FieldSpec> nodeFields;  // shown in the node mask if the node has this role

  const RoleSpec(this.key, this.defaultRole, this.nodeFields);

  String get label => 'role.$defaultRole';
}

enum NetworkUse { none, optional, required }

/// Column of a result table - key is the field in the llsol file, label result.<key>.
class ResultColumn {
  final String key;
  final String? unit;
  const ResultColumn(this.key, {this.unit});

  String get label => 'result.$key';
}

class ModuleSpec {
  final String type;                 // problem type of the llab file
  final ModuleGroup group;
  final List<RoleSpec> roles;
  final List<FieldSpec> parameters;
  final NetworkUse network;
  final List<FieldSpec> edgeFields;  // attributes of the edges used by this problem type
  final bool usesMatrix;             // distances, times or costs from OSM (matrixMode)
  final List<ResultColumn> summary;
  final List<ResultColumn> nodeResults;
  final List<ResultColumn> assignments;   // rows from -> to, e.g. flows of a tpp

  const ModuleSpec({
    required this.type,
    required this.group,
    required this.roles,
    required this.parameters,
    this.network = NetworkUse.none,
    this.edgeFields = const [],
    this.usesMatrix = true,
    this.summary = const [],
    this.nodeResults = const [],
    this.assignments = const [],
  });

  String get label => 'module.$type';
  String get description => 'module.$type.description';
  String get groupLabel => 'group.${group.name}';

  /// Parameters of a new problem of this type.
  Map<String, dynamic> defaultParameters() =>
      {for (final f in parameters) if (f.defaultValue != null) f.key: f.defaultValue};

  /// Node role of a role of the problem, e.g. sources -> supplier.
  String nodeRole(RoleSpec role, Map<String, dynamic> parameters) =>
      (parameters['roles'] as Map?)?[role.key] as String? ?? role.defaultRole;

  /// Fields of the node mask for a node with the given roles - each field only once.
  List<FieldSpec> nodeFieldsFor(Iterable<String> nodeRoles, Map<String, dynamic> parameters) {
    final seen = <String>{};
    return [
      for (final r in roles)
        if (nodeRoles.contains(nodeRole(r, parameters)))
          for (final f in r.nodeFields)
            if (f.isVisible(parameters) && seen.add(f.key)) f
    ];
  }

  /// Fields of the parameter form - e.g. without minSupply if it does not apply.
  Iterable<FieldSpec> visibleParameters(Map<String, dynamic> values) => parameters.where((f) => f.isVisible(values));

  List<Message> validateParameters(Map<String, dynamic> values) => [
        for (final f in visibleParameters(values))
          if (f.validate(values[f.key] ?? f.defaultValue) case final Message msg) msg
      ];

  /// All message keys of the module - must be in every language file (bin/i18n_check.dart).
  Set<String> get messageKeys => {
        label, description, groupLabel,
        for (final r in roles) ...[r.label, for (final f in r.nodeFields) ...f.messageKeys],
        for (final f in [...parameters, ...edgeFields]) ...f.messageKeys,
        for (final c in [...summary, ...nodeResults, ...assignments]) c.label,
      };
}

//*************** common fields ************************************

const errorKeys = ['error.required', 'error.number', 'error.integer', 'error.min', 'error.boolean', 'error.choice',
  'error.text'];

const objSenseField =
    FieldSpec('objSense', FieldKind.choice, defaultValue: 'min', choices: ['min', 'max', 'minimax']);

const matrixModeField = FieldSpec('matrixMode', FieldKind.choice, choices: ['distances', 'times', 'costs']);

const solverFields = [
  FieldSpec('maxSolvingTime', FieldKind.number, unit: 's', min: 1),
  FieldSpec('mipGap', FieldKind.number, min: 0),
];

bool _on(Map<String, dynamic> p, String key) => p[key] == true;

//*************** transportation problem ************************************

final tppSpec = ModuleSpec(
  type: 'tpp',
  group: ModuleGroup.transport,
  roles: [
    RoleSpec('sources', 'supplier', [
      const FieldSpec('supply', FieldKind.number, required: true, min: 0),
      FieldSpec('minSupply', FieldKind.number, min: 0, visibleIf: (p) => _on(p, 'useSupplyRanges')),
      FieldSpec('maxSupply', FieldKind.unlimited, min: 0, visibleIf: (p) => _on(p, 'useSupplyRanges')),
    ]),
    RoleSpec('destinations', 'customer', [
      const FieldSpec('demand', FieldKind.number, required: true, min: 0),
      FieldSpec('minDemand', FieldKind.number, min: 0, visibleIf: (p) => _on(p, 'useDemandRanges')),
      FieldSpec('maxDemand', FieldKind.unlimited, min: 0, visibleIf: (p) => _on(p, 'useDemandRanges')),
      const FieldSpec('costFactor', FieldKind.number, defaultValue: 1.0, min: 0),
    ]),
  ],
  parameters: [
    objSenseField,
    matrixModeField,
    const FieldSpec('isSingleSource', FieldKind.boolean, defaultValue: false),
    const FieldSpec('minBlock', FieldKind.number, min: 0),
    const FieldSpec('maxBlock', FieldKind.unlimited, min: 0),
    const FieldSpec('useSupplyRanges', FieldKind.boolean, defaultValue: false),
    const FieldSpec('useDemandRanges', FieldKind.boolean, defaultValue: false),
    const FieldSpec('useCapacities', FieldKind.boolean, defaultValue: false),
    const FieldSpec('useFixedCosts', FieldKind.boolean, defaultValue: false),
    ...solverFields,
  ],
  network: NetworkUse.optional,
  edgeFields: [
    FieldSpec('capacity', FieldKind.unlimited, min: 0, visibleIf: (p) => _on(p, 'useCapacities')),
    FieldSpec('fixedCost', FieldKind.number, unit: '€', min: 0, visibleIf: (p) => _on(p, 'useFixedCosts')),
  ],
  summary: const [
    ResultColumn('totalCosts', unit: '€'),
    ResultColumn('totalVarCosts', unit: '€'),
    ResultColumn('totalFixedCosts', unit: '€'),
    ResultColumn('totalFlow'),
    ResultColumn('minCostRate'),
    ResultColumn('maxCostRate'),
  ],
  nodeResults: const [ResultColumn('flow')],
  assignments: const [ResultColumn('flow'), ResultColumn('rate')],
);

/// All modules of the UI - the menu "new problem" of the problem chooser groups them by ModuleGroup.
final modules = {for (final m in [tppSpec]) m.type: m};

Map<ModuleGroup, List<ModuleSpec>> modulesByGroup() =>
    {for (final g in ModuleGroup.values) g: [for (final m in modules.values) if (m.group == g) m]};

/// Message keys of all modules and of the common texts.
Set<String> allMessageKeys() => {
      for (final g in ModuleGroup.values) 'group.${g.name}',
      ...errorKeys,
      for (final m in modules.values) ...m.messageKeys,
    };

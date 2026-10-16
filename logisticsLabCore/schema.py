""" JSON Schema of all requests - e.g. to generate the Dart models of the Flutter app

    python -m logisticsLabCore.schema > logisticsLab.schema.json

    The same items are used by the REST server and by the local stdio interface.
"""

from .items import *

import json

from pydantic.json_schema import models_json_schema


def schema():
    items = list(PROBLEM_ITEMS.values()) + list(GEO_ITEMS.values()) + [ResultItem]
    _, defs = models_json_schema([(i, 'validation') for i in items], title='LogisticsLab')
    return defs


if __name__ == '__main__':
    print(json.dumps(schema(), indent=2, ensure_ascii=False))

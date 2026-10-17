""" JSON Schema of all requests and answers - e.g. to generate the Dart models of the Flutter app

    python -m logisticsLabCore.schema > logisticsLab.schema.json

    The same items are used by the REST server and by the local stdio interface.
    The results of a problem type are described by RESULT_ITEMS (e.g. contpcentre -> ContLocationResults).
"""

from .items import *
from .results import RESULT_ITEMS, ProblemAnswer

import json

from pydantic.json_schema import models_json_schema


def schema():
    results = list(dict.fromkeys(RESULT_ITEMS.values()))       # unique, in the order of the types
    items = list(PROBLEM_ITEMS.values()) + list(GEO_ITEMS.values()) + [ResultItem, ProblemAnswer] + results
    _, defs = models_json_schema([(i, 'validation') for i in items], title='LogisticsLab')
    return defs


if __name__ == '__main__':
    print(json.dumps(schema(), indent=2, ensure_ascii=False))

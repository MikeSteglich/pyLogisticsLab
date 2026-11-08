""" order of the geocoding hits (osm_data/geocoding.py) without OSM servers

    python tests/coreTests/checkGeocodingOrder.py

    the hit that fits the address best comes first - a typing error in the street (Haupstraße) must not lead to
    another house of the place that photon puts first; equal hits keep the order of the server
"""

import sys

from osm_data.geocoding import addressScore, orderHits


nrOfErrors = 0

def check(name, isOk, info=''):
    global nrOfErrors
    if not isOk:
        nrOfErrors += 1
    print(f"{'ok    ' if isOk else 'FAILED'} {name} {info}")


def hit(street, city='Oranienburg', postcode='16515', district='Wensickendorf', name=''):
    return {'name': name, 'street': street, 'postcode': postcode, 'city': city, '_district': district}


# photon: the first hit of 'Wensickendorf, 16515, Haupstraße 9' is Triftweg 9
hits = [hit('Triftweg 9'), hit('Hauptstraße 9'), hit('Kastanienallee 9')]
first = orderHits('Wensickendorf, 16515, Haupstraße 9', hits)[0]
check('typing error in the street', first['street'] == 'Hauptstraße 9', first['street'])

first = orderHits('Hauptstr. 9, 16515 Wensickendorf', [hit('Hauptstraße 19'), hit('Hauptstraße 9')])[0]
check('abbreviated street and house number', first['street'] == 'Hauptstraße 9', first['street'])

# equal hits: the order of the server (relevance, near the other nodes)
hits = [hit('Hauptstraße 9', 'Wildau', '15745', ''), hit('Hauptstraße 9', 'Berlin', '10115', 'Mitte')]
check('equal hits keep their order', orderHits('Hauptstraße 9', hits) == hits)

hits = [{'name': 'Berlin', 'city': ''}, hit('Berliner Straße 1', 'Berlin', '10115', '')]
check('a place stays before a street named after it', orderHits('Berlin', hits) == hits)

# short words only if equal: DE is not 'der' of An der Lützen (photon puts the town first)
hits = [{'name': 'Lützen', 'postcode': '06686'}, {'name': 'An der Lützen', 'postcode': '53639', 'city': 'Königswinter'}]
first = orderHits('Lützen, DE', hits)[0]
check('short words', first['name'] == 'Lützen', first['name'])

check('score of the exact address', addressScore('Hauptstraße 9, Wensickendorf', hit('Hauptstraße 9')) == 1.0)
check('no words', addressScore('', hit('Hauptstraße 9')) == 0.0)

print(f'{nrOfErrors} errors')
sys.exit(1 if nrOfErrors else 0)

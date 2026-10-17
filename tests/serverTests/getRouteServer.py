from logLabClient import request, showResults

# route via the LogisticsLab server (/v1/routing, service routing) - coordinates [lat, lon]
endpoint = 'routing'
payloads = []

# Berlin: Brandenburger Tor - Alexanderplatz - Ostbahnhof by car
payloads.append({
    "coordinates": [[52.516275, 13.377704], [52.521918, 13.413215], [52.510972, 13.434567]],
    "travelmode": "car",
    "details": "simplified"
})

# Eberswalde with all points of the route - foot and wheelchair need OSM servers with these profiles,
# the servers of the TH Wildau (logisticsLab.yml) only provide car
payloads.append({
    "coordinates": [[52.824443, 13.782697], [52.821606, 13.784162]],
    "travelmode": "car",
    "details": "full"
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        code, ret = request(endpoint, payload)
        showResults(ret, f'{endpoint} - request {k+1} of {len(payloads)} - http {code}')

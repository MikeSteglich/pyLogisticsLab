from logLabClient import request, showResults

# distance and time matrix via the LogisticsLab server (/v1/matrix, service matrix) - coordinates [lat, lon]
endpoint = 'matrix'
payloads = []

coordinates = [[52.516275, 13.377704], [52.521918, 13.413215], [52.510972, 13.434567], [52.39, 13.06]]

# all to all, distances (m) and durations (s)
payloads.append({"coordinates": coordinates, "travelmode": "car", "matrixMode": "both", "rounded": True})

# only from the first two to the last two coordinates
payloads.append({"coordinates": coordinates, "sources": [0, 1], "destinations": [2, 3], "matrixMode": "distances"})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        code, ret = request(endpoint, payload)
        showResults(ret, f'{endpoint} - request {k+1} of {len(payloads)} - http {code}')

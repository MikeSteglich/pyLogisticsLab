from logLabClient import request, showResults

# coordinates [lat, lon] of addresses via the LogisticsLab server (/v1/coordinates, service geocoding)
endpoint = 'coordinates'
payloads = [{"adresses": ['Schönwalde,16348,DE', 'Klosterfelde', 'Marchlewskistr. 43, 10243 Berlin']}]


if __name__ == '__main__':
    for payload in payloads:
        code, ret = request(endpoint, payload)
        showResults(ret, f'{endpoint} - http {code}')

from logLabClient import request, showResults

# address of a coordinate [lat, lon] via the LogisticsLab server (/v1/reverse, service geocoding)
endpoint = 'reverse'
payloads = [{"coordinate": [52.7965937, 13.4801974]}]


if __name__ == '__main__':
    for payload in payloads:
        code, ret = request(endpoint, payload)
        showResults(ret, f'{endpoint} - http {code}')

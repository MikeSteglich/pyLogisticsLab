from logLabClient import request, showResults

# search for an address via the LogisticsLab server (/v1/search, service geocoding)
endpoint = 'search'
payloads = [{"adress": 'Schönwalde,16348,DE'}]


if __name__ == '__main__':
    for payload in payloads:
        code, ret = request(endpoint, payload)
        showResults(ret, f'{endpoint} - http {code}')

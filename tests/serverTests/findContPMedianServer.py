from logLabClient import solve, showResults

endpoint = 'contpmedian'
payloads = []

# continuous p-median: 3 facilities anywhere in Brandenburg, great-circle distances in km
coordinates = [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
               [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]]
demands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8]

payloads.append({"p": 3, "coordinates": coordinates, "demands": demands})

# capacitated, the demand of a customer can be split
payloads.append({"p": 3, "coordinates": coordinates, "demands": demands, "capacities": 100, "isSingleSource": False})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

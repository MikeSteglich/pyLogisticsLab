from logLabClient import solve, showResults

endpoint = 'contpcentre'
payloads = []

# continuous p-centre: 3 facilities anywhere in Brandenburg - minimizes the largest great-circle distance (km)
coordinates = [[52.39, 13.06], [52.52, 13.40], [52.41, 12.55], [52.34, 14.55], [51.76, 14.33], [53.03, 13.99],
               [52.93, 12.80], [52.60, 13.25], [51.97, 13.15], [52.76, 13.61], [52.12, 14.11], [52.84, 14.06]]
demands = [20, 80, 15, 25, 30, 10, 12, 18, 9, 14, 11, 8]

payloads.append({"p": 3, "coordinates": coordinates})

# capacitated, single-source
payloads.append({"p": 3, "coordinates": coordinates, "demands": demands, "capacities": [100, 100, 60]})


def evaluate(payload, ret):
    """ example of further processing - the results are a dict, indices are 0-based positions of the input """
    if ret.get('status') != 'solution':
        print('no solution:', ret.get('status'), ret.get('message', ret))
        return

    r = ret['results']
    objVal = r['objVal']                        # largest distance in km
    locations = r['locations']                  # [[lat, lon], ...] of every facility
    assignments = r['assignments']              # facility of every customer
    customerDistances = r['customerDistances']  # km of every customer to its facility

    print(f'largest distance {objVal:.2f} km')

    # customers of every facility and, if capacitated, the load of the facility
    capacities = payload.get('capacities')
    for k, (lat, lon) in enumerate(locations):
        customers = [ j for j, a in enumerate(assignments) if a == k ]
        line = f'facility {k} ({lat:.4f}, {lon:.4f}): customers {customers}'
        if capacities is not None:
            load = sum(payload['demands'][j] for j in customers)
            cap = capacities[k] if isinstance(capacities, list) else capacities
            line += f', load {load} of {cap}'
        print(line)

    # the customer with the largest distance determines the objective value
    worst = max(range(len(customerDistances)), key=lambda j: customerDistances[j])
    print(f'farthest customer {worst} {payload["coordinates"][worst]}: {customerDistances[worst]:.2f} km '
          f'to facility {assignments[worst]}')
    print()


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')
        evaluate(payload, ret)

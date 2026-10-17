from logLabClient import solve, showResults

endpoint = 'vrp'
payloads = []

# vehicle routing: depot 0, 4 customers, 2 vehicles with capacity 10
payloads.append({
    "distances": [[0, 4, 7, 5, 6], [4, 0, 3, 6, 8], [7, 3, 0, 4, 7], [5, 6, 4, 0, 3], [6, 8, 7, 3, 0]],
    "demands": [0, 4, 5, 3, 6],
    "capacities": [10, 10],
    "depot": 0,
    "maxSolvingTime": 2
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

from logLabClient import solve, showResults

endpoint = 'wlp'
payloads = []

# warehouse location: 3 possible warehouses, 4 customers
payloads.append({
    "varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
    "fixedCosts": [5000, 4000, 6000],
    "demands": [600, 400, 200, 150],
    "supplies": [800, 700, 600],
    "isCapacitated": True
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

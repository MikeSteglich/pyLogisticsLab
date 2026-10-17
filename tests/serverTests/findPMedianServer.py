from logLabClient import solve, showResults

endpoint = 'pmedian'
payloads = []

# p-median: open 2 of 3 sources for 4 destinations, distances weighted with the demands
payloads.append({
    "p": 2,
    "varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
    "demands": [6, 4, 2, 1],
    "isDemandWeighted": True
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

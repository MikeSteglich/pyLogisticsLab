from logLabClient import solve, showResults

endpoint = 'mcp'
payloads = []

# maximal covering: open 1 source (fixed costs 1), maximal demand within radius 3
payloads.append({
    "distances": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
    "radius": 3,
    "demands": [6, 4, 2, 1],
    "maxSrcCost": 1
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

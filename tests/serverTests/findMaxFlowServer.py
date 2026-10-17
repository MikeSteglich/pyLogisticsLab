from logLabClient import solve, showResults

endpoint = 'maxflow'
payloads = []

# maximal flow from node 0 to node 3
payloads.append({
    "edges": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
    "source": 0,
    "sink": 3,
    "maxCaps": [15, 8, 20, 5, 10]
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

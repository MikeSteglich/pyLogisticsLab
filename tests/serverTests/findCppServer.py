from logLabClient import solve, showResults

endpoint = 'cpp'
payloads = []

# chinese postman: undirected graph, every edge has to be used at least once
payloads.append({
    "edges": [[1, 2], [2, 3], [3, 4], [4, 1], [1, 3]],
    "edgeWeights": [4, 3, 5, 2, 6],
    "startNode": 1
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

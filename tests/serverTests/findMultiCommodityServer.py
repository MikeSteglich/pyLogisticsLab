from logLabClient import solve, showResults

endpoint = 'multicommodity'
payloads = []

# 2 commodities from node 0 to node 3 with joint capacities of the edges
payloads.append({
    "edges": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
    "costs": [[4, 1], [4, 1], [2, 1], [2, 1], [1, 1]],           # [edges x commodities]
    "supplies": [[10, 5], [0, 0], [0, 0], [0, 0]],              # [nodes x commodities]
    "demands": [[0, 0], [0, 0], [0, 0], [10, 5]],
    "maxCaps": [15, 8, 20, "M", 10]
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

from logLabClient import solve, showResults

endpoint = 'mincostflow'
payloads = []

# min cost flow: node 0 supplies 20 units, nodes 2 and 3 demand 5 and 15
payloads.append({
    "edges": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
    "costs": [4, 4, 2, 2, 1],
    "supplies": [20, 0, 0, 0],
    "demands": [0, 0, 5, 15],
    "maxCaps": [15, 8, 20, 5, 10]           # null or "M": unlimited
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

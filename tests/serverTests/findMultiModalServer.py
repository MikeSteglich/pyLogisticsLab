from logLabClient import solve, showResults

endpoint = 'multimodal'
payloads = []

# truck and train - the train has fixed costs and a minimal load of 10, it is not available on every edge
payloads.append({
    "edges": [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]],
    "costs": [[4, 1], [4, None], [2, None], [2, 1], [1, None]],  # [edges x modes], null: mode not available
    "supplies": [20, 0, 0, 0],
    "demands": [0, 0, 5, 15],
    "fixedCosts": [[0, 30], [0, 0], [0, 0], [0, 30], [0, 0]],
    "minCaps": [[0, 10], [0, 0], [0, 0], [0, 10], [0, 0]]
})


if __name__ == '__main__':
    for k, payload in enumerate(payloads):
        ret = solve(endpoint, payload, verbose=False)
        showResults(ret, endpoint if len(payloads) == 1 else f'{endpoint} - problem {k+1} of {len(payloads)}')

import heapq

def route(state, origin, destination, emergency=False):
    """Undirected shortest travel time. A closed gate is not a transit shortcut."""
    closed = {g['id'] for g in state['gates'] if g['closed']}
    if destination in closed and not emergency:
        return None
    graph = {}
    for edge in state['edges']:
        a, b = edge['from'], edge['to']
        # Responders may enter the incident destination from its approach lane only.
        if any(x in closed and x != origin and not (emergency and x == destination) for x in (a, b)):
            continue
        graph.setdefault(a, []).append((b, edge['seconds']))
        graph.setdefault(b, []).append((a, edge['seconds']))
    queue, best = [(0, origin, [origin])], {origin: 0}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == destination:
            return {'nodes': path, 'seconds': cost}
        for nxt, weight in graph.get(node, []):
            val = cost + weight
            if val < best.get(nxt, 10**9):
                best[nxt] = val
                heapq.heappush(queue, (val, nxt, path + [nxt]))
    return None

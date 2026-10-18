def dedupe(rows):
    """A later row with the same (order_id, line) replaces the earlier one but keeps its position."""
    result, index = [], {}
    for r in rows:
        key = (r.order_id, r.line)
        i = index.get(key)
        if i is None:
            index[key] = len(result)
            result.append(r)
        else:
            result[i] = r
    return result


def drop_cancelled(rows):
    return [r for r in rows if r.status != "cancel"]

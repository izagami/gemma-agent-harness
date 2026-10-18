def dedupe(rows):
    """A later row with the same (order_id, line) replaces the earlier one but keeps its position."""
    result = []
    for r in rows:
        for i, existing in enumerate(result):
            if existing.order_id == r.order_id and existing.line == r.line:
                result[i] = r
                break
        else:
            result.append(r)
    return result


def drop_cancelled(rows):
    out = []
    for r in rows:
        if r.status != "cancel":
            out = out + [r]
    return out

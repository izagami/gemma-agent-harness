def split_name(full):
    """'Yamada Taro' -> ('Yamada', 'Taro')  (family name first)."""
    parts = full.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return parts[-1], " ".join(parts[:-1])


def split_tags(text):
    if not text:
        return []
    return text.split(",")

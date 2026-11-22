import re


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.strip().lower())
    return s.strip("-")

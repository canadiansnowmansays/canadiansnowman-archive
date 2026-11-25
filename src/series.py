"""Decide which series each essay belongs to.

Order of authority, first match wins:
  1. src/series_overrides.json   - hand corrections: {"<post number>": "Series Name"}
  2. the Substack section the post was filed under (posts.json "section")
  3. the May 2026 archive's assignments (src/data/may_map.json)
  4. the title prefix before the colon, matched against series.json names/aliases
  5. "Essays & Dispatches"
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CATCH_ALL = "Essays & Dispatches"


def _load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"').lower()
    s = re.sub(r"\b(part|essay|no\.?)\s*[ivxlc\d]+\b.*$", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    return s


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("&", "")).strip("-")


SERIES = _load("series.json", [])
OVERRIDES = _load("series_overrides.json", {})
MAY = _load("data/may_map.json", {})

ALIAS = {}
for s in SERIES:
    for a in [s["name"]] + s.get("aliases", []) + s.get("sections", []):
        ALIAS.setdefault(norm(a), s["name"])
SECTION = {}
for s in SERIES:
    for a in [s["name"]] + s.get("sections", []):
        SECTION[norm(a)] = s["name"]


def assign(p):
    num = p["num"]
    if num in OVERRIDES:
        return OVERRIDES[num]
    sec = p.get("section")
    if sec:
        return SECTION.get(norm(sec), sec)
    if num in MAY:
        return ALIAS.get(norm(MAY[num]), MAY[num])
    t = p["title"]
    for sep in (":", " — ", " - "):
        if sep in t:
            hit = ALIAS.get(norm(t.split(sep)[0]))
            if hit:
                return hit
    return CATCH_ALL

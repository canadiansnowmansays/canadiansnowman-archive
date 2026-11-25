"""Bring src/data up to date from the public Substack archive.

Usage:
  python src/update.py          add essays published since the last run
  python src/update.py --full   also re-check every essay's title, subtitle and
                                series, and refresh series descriptions/images

Runs automatically on GitHub (see .github/workflows/publish.yml).
"""
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from clean import clean  # noqa: E402
from substack import PUB, UA, archive, feed, post  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PJ = os.path.join(DATA, "posts.json")
SJ = os.path.join(HERE, "series.json")


def fetch_section_meta():
    """Every section's name, slug, description and image, from a section page."""
    req = urllib.request.Request(f"{PUB}/archive", headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    i = page.find('"sections":[')
    if i < 0:
        return []
    arr, _ = json.JSONDecoder().raw_decode(page[i + len('"sections":'):])
    return arr


def refresh_series(posts):
    series = json.load(open(SJ, encoding="utf-8"))
    names = {s["name"] for s in series}
    needed = {p["section"] for p in posts if p.get("section")}
    try:
        meta = {m["name"].strip(): m for m in fetch_section_meta()}
    except Exception as e:
        print("could not read section details:", e)
        meta = {}
    changed = False
    for s in series:
        m = meta.get(s["name"])
        if m:
            for k, v in (("slug", m.get("slug")), ("description", (m.get("description") or "").strip()), ("image", m.get("logo_url") or "")):
                if v and s.get(k) != v:
                    s[k] = v
                    changed = True
    for name in sorted(needed - names):
        m = meta.get(name, {})
        series.append({"name": name, "short": name.split(":")[0].strip(), "sections": [name], "aliases": [],
                       "parent": None, "order": "oldest", "slug": m.get("slug", ""),
                       "description": (m.get("description") or "").strip(), "image": m.get("logo_url") or ""})
        print("new series:", name)
        changed = True
    if changed:
        series.sort(key=lambda s: s["name"].lower())
        json.dump(series, open(SJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# Every publication the archive collects. A publication with a "series" puts all
# its posts in that one series; otherwise each post's Substack section decides.
PUBLICATIONS = [
    {"url": PUB, "series": None},
    {"url": "https://stephengordon1951.substack.com", "series": "Sketches of Elsinore"},
]


def to_post(api, pubinfo):
    pub = pubinfo["url"]
    html_body = api.get("body_html") or ""
    if len(html_body) < 500:  # the archive list carries no full text; fetch the post itself
        html_body = post(api["slug"], pub).get("body_html") or ""
    body, cover, words = clean(html_body)
    num = str(api.get("id") or api["slug"])  # feed posts carry no id: key them by slug
    with open(os.path.join(DATA, "posts", num + ".html"), "w", encoding="utf-8") as f:
        f.write(body)
    p = {
        "num": num,
        "slug": api["slug"],
        "date": api["post_date"],
        "title": (api.get("title") or "").strip(),
        "subtitle": (api.get("subtitle") or "").strip(),
        "cover": cover or api.get("cover_image") or "",
        "words": words or api.get("wordcount") or 0,
        "section": pubinfo["series"] or (api.get("section_name") or "").strip(),
    }
    if pub != PUB:
        p["pub"] = pub
    return p


def update_pub(pubinfo, known, full):
    pub = pubinfo["url"]
    mine = {n for n, p in known.items() if p.get("pub", PUB) == pub}
    added = 0
    try:
        if full:
            seen = set()
            for api in archive(pub=pub):
                num = str(api["id"])
                seen.add(num)
                if api["slug"] in known and known[api["slug"]].get("pub", PUB) == pub:
                    known.pop(api["slug"])  # came in through the feed: re-key it by its Substack number
                    os.remove(os.path.join(DATA, "posts", api["slug"] + ".html"))
                    known[num] = to_post(api, pubinfo)
                    continue
                if num not in known:
                    known[num] = to_post(api, pubinfo)
                    added += 1
                    continue
                p = known[num]
                section = pubinfo["series"] or api.get("section_name")
                for k, v in (("title", api.get("title")), ("subtitle", api.get("subtitle")), ("section", section)):
                    v = (v or "").strip()
                    if v != p.get(k, ""):
                        p[k] = v
            gone = mine - seen
            if gone and len(gone) < 50:  # unpublished on Substack: keep the backup, but note it
                print("no longer on Substack (kept in archive):", ", ".join(sorted(gone)))
        else:
            for api in archive(stop_at=mine, pub=pub):
                known[str(api["id"])] = to_post(api, pubinfo)
                added += 1
    except Exception as e:
        # Substack sometimes refuses its API to cloud servers; the public RSS feed still works
        print(f"{pub}: archive API unavailable ({e}); using the RSS feed instead")
        slugs = {p["slug"] for p in known.values() if p.get("pub", PUB) == pub}
        for api in feed(pub):
            if api["slug"] not in slugs:
                p = to_post(api, pubinfo)
                known[p["num"]] = p
                added += 1
    print(f"{pub}: {added} new")
    return added


def main(full=False):
    posts = json.load(open(PJ, encoding="utf-8"))
    known = {p["num"]: p for p in posts}
    added = 0
    for pubinfo in PUBLICATIONS:
        try:
            added += update_pub(pubinfo, known, full)
        except Exception as e:
            print(f"{pubinfo['url']}: not updated ({e})")
    posts = sorted(known.values(), key=lambda p: p["date"])
    json.dump(posts, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    try:
        refresh_series(posts)
    except Exception as e:
        print("series details not refreshed:", e)
    print(f"{added} new essay(s); archive now holds {len(posts)}")


if __name__ == "__main__":
    main(full="--full" in sys.argv)

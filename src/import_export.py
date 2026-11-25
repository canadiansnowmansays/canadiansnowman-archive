"""One-time import of a Substack export folder into src/data/.

Usage: python src/import_export.py /path/to/unzipped-export

Reads posts.csv + posts/*.html, keeps published posts, cleans each body and
writes src/data/posts/<number>.html and src/data/posts.json. The subscriber
list in the export is never read or copied.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from clean import clean  # noqa: E402
from series import assign  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def main(export_dir):
    os.makedirs(os.path.join(DATA, "posts"), exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(export_dir, "posts.csv"), encoding="utf-8")))
    posts = []
    existing = {}
    pj = os.path.join(DATA, "posts.json")
    if os.path.exists(pj):
        existing = {p["num"]: p for p in json.load(open(pj, encoding="utf-8"))}
    for r in rows:
        if r.get("is_published") != "true":
            continue
        num, _, slug = r["post_id"].partition(".")
        src = os.path.join(export_dir, "posts", r["post_id"] + ".html")
        if not os.path.exists(src):
            print("missing body:", r["post_id"])
            continue
        body, cover, words = clean(open(src, encoding="utf-8").read())
        with open(os.path.join(DATA, "posts", num + ".html"), "w", encoding="utf-8") as f:
            f.write(body)
        old = existing.get(num, {})
        posts.append({
            "num": num,
            "slug": slug,
            "date": r["post_date"],
            "title": r["title"].strip(),
            "subtitle": (r.get("subtitle") or "").strip(),
            "cover": cover,
            "words": words,
            "section": old.get("section", ""),  # Substack section name, filled by fetch_sections.py
        })
    posts.sort(key=lambda p: p["date"])
    for p in posts:
        p["series"] = assign(p)
    json.dump(posts, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"imported {len(posts)} published posts")


if __name__ == "__main__":
    main(sys.argv[1])

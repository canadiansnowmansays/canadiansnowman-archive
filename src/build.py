"""Build the static archive site from src/data into an output folder.

Usage: python src/build.py _site
Then:  npx pagefind --site _site   (adds full-text search)

URL scheme matches the May 2026 site so old links keep working:
  posts/<number>/   sections/<slug>/   chronological/   search/
"""
import datetime as dt
import html
import re
import json
import os
import shutil
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from clean import cdn  # noqa: E402
from series import CATCH_ALL, SERIES, assign, slugify  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SITE_NAME = "Canadian Snowman Says"
AUTHOR = "Stephen Gordon"
SUBSTACK = "https://canadiansnowmansays.substack.com"
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

e = html.escape


def fmt_date(iso, long=True):
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=-5)))
    return d.strftime("%-d %B %Y") if long else d.strftime("%-d %b %Y")


def month_key(iso):
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=-5)))
    return d.strftime("%Y-%m"), d.strftime("%B %Y")


def thumb(src, w=480, h=300):
    return cdn(src, w, h, crop=True) if src else ""


def page(rel, title, body, desc="", extra_head="", active=""):
    """Wrap body in the site chrome. rel = path prefix back to site root."""
    nav = [("", "Home"), ("sections/", "Series"), ("ledgers/", "Ledgers"), ("chronological/", "By date"), ("search/", "Search")]
    links = "".join(
        f'<a href="{rel}{h}"{" class=active" if active == lbl else ""}>{lbl}</a>' for h, lbl in nav
    )
    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="stylesheet" href="{rel}assets/site.css">
<link rel="icon" href="{rel}assets/snowflake.svg" type="image/svg+xml">
{extra_head}
</head>
<body>
<header class="masthead">
  <a class="brand" href="{rel}"><img src="{rel}assets/snowflake.svg" alt="" width="26" height="26"><span>{SITE_NAME}</span><small>The Archive</small></a>
  <nav>{links}</nav>
</header>
<main>
{body}
</main>
<footer class="foot">
  <p>Essays by {AUTHOR}, written in open collaboration with Claude. First published on Substack at <a href="{SUBSTACK}">CanadianSnowmanSays</a> and <a href="https://stephengordon1951.substack.com">Sketches of Elsinore</a>; this archive is an independent backup, rebuilt automatically every day.</p>
</footer>
</body>
</html>
"""


def card(p, rel, show_series=True):
    img = f'<img src="{e(thumb(p["cover"]))}" alt="" loading="lazy">' if p["cover"] else '<div class="noimg"></div>'
    ser = f'<span class="kicker">{e(p["series_short"])}</span>' if show_series else ""
    return f"""<a class="card" href="{rel}posts/{p['num']}/">{img}<div class="cardtext">{ser}<h3>{e(p['title'])}</h3><p class="sub">{e(p['subtitle'])}</p><p class="meta">{fmt_date(p['date'], False)}</p></div></a>"""


def row(p, rel, n=None):
    img = f'<img src="{e(thumb(p["cover"], 240, 160))}" alt="" loading="lazy">' if p["cover"] else '<div class="noimg"></div>'
    num = f'<span class="num">{n}</span>' if n else ""
    return f"""<li><a href="{rel}posts/{p['num']}/">{img}<div>{num}<h3>{e(p['title'])}</h3><p class="sub">{e(p['subtitle'])}</p><p class="meta">{fmt_date(p['date'])} · {max(1, round(p['words'] / 230))} min read</p></div></a></li>"""


def build(out):
    posts = json.load(open(os.path.join(DATA, "posts.json"), encoding="utf-8"))
    posts.sort(key=lambda p: p["date"])
    meta = {s["name"]: s for s in SERIES}

    def sslug(name):
        return meta.get(name, {}).get("slug") or slugify(name)
    for p in posts:
        p["series"] = assign(p)
        s = meta.get(p["series"], {})
        p["series_short"] = s.get("short", p["series"])
        p["series_slug"] = sslug(p["series"])

    by = OrderedDict()
    for p in posts:
        by.setdefault(p["series"], []).append(p)
    for name, ps in by.items():
        if meta.get(name, {}).get("order") == "newest":
            ps.reverse()

    children = defaultdict(list)
    for name in by:
        parent = meta.get(name, {}).get("parent")
        if parent:
            children[parent].append(name)

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(out, "assets"))
    open(os.path.join(out, ".nojekyll"), "w").close()

    def write(path, text):
        full = os.path.join(out, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    # ---------- public ledgers ----------
    ldir = os.path.join(HERE, "ledgers")
    ledgers = json.load(open(os.path.join(ldir, "ledgers.json"), encoding="utf-8")) if os.path.isdir(ldir) else []
    ledger_for = {l["series"]: l for l in ledgers if l.get("series") and l.get("file")}
    bar = ('<div style="position:sticky;top:0;z-index:99999;display:flex;gap:1rem;justify-content:space-between;align-items:center;'
           'padding:.45rem 1rem;background:#1b2430;color:#fff;font:600 13px/1.4 system-ui,-apple-system,Segoe UI,sans-serif">'
           '<a href="../../" style="color:#fff;text-decoration:none">❄ Canadian Snowman Says · The Archive</a>'
           '<a href="../" style="color:#f3c2c5;text-decoration:none">All ledgers →</a></div>')
    for l in ledgers:
        if not l.get("file"):
            continue
        h = open(os.path.join(ldir, l["file"] + ".html"), encoding="utf-8").read()
        h = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + bar, h, count=1, flags=re.I)
        write(f"ledgers/{l['file']}/index.html", h)

    # ---------- essay pages ----------
    for name, ps in by.items():
        chrono = sorted(ps, key=lambda p: p["date"])
        total = len(chrono)
        for i, p in enumerate(chrono):
            prev_p = chrono[i - 1] if i > 0 else None
            next_p = chrono[i + 1] if i + 1 < total else None
            body = open(os.path.join(DATA, "posts", p["num"] + ".html"), encoding="utf-8").read()
            pn = []
            if prev_p:
                pn.append(f'<a class="prev" href="../{prev_p["num"]}/"><span>← Previous in this series</span>{e(prev_p["title"])}</a>')
            else:
                pn.append('<span class="prev empty"></span>')
            if next_p:
                pn.append(f'<a class="next" href="../{next_p["num"]}/"><span>Next in this series →</span>{e(next_p["title"])}</a>')
            parent = meta.get(name, {}).get("parent")
            crumbs = f'<a href="../../">Home</a> › '
            if parent and parent in by:
                crumbs += f'<a href="../../sections/{sslug(parent)}/">{e(meta.get(parent, {}).get("short", parent))}</a> › '
            crumbs += f'<a href="../../sections/{p["series_slug"]}/">{e(p["series_short"])}</a>'
            pos = f"Essay {i + 1} of {total}" if name != CATCH_ALL else "Standalone essay"
            hero = f'<meta property="og:image" content="{e(cdn(p["cover"], 1200))}">' if p["cover"] else ""
            art = f"""<article class="essay">
<p class="crumbs">{crumbs}</p>
<header data-pagefind-body-exclude>
<h1 data-pagefind-meta="title">{e(p['title'])}</h1>
{f'<p class="subtitle">{e(p["subtitle"])}</p>' if p['subtitle'] else ''}
<p class="byline">{AUTHOR} · {fmt_date(p['date'])} · {max(1, round(p['words'] / 230))} min read · {pos}</p>
</header>
<div class="prose" data-pagefind-body>
<p class="pf-hidden" data-pagefind-filter="series">{e(p['series_short'])}</p>
{f'<img class="pf-hidden" data-pagefind-meta="image[src]" src="{e(thumb(p["cover"], 240, 160))}" alt="">' if p['cover'] else ''}
{body}
</div>
<p class="original"><a href="{p.get('pub', SUBSTACK)}/p/{e(p['slug'])}">Read this essay on Substack, with comments →</a></p>
<nav class="prevnext">{''.join(pn)}</nav>
</article>"""
            write(f"posts/{p['num']}/index.html",
                  page("../../", f"{p['title']} · {SITE_NAME}", art, p["subtitle"], hero))

    # ---------- series pages ----------
    def series_card(name, rel):
        ps = by[name]
        latest = max(ps, key=lambda p: p["date"])
        first = min(ps, key=lambda p: p["date"])
        n = len(ps) + sum(len(by[c]) for c in children.get(name, []))
        pic = meta.get(name, {}).get("image") or latest["cover"]
        img = f'<img src="{e(thumb(pic))}" alt="" loading="lazy">' if pic else '<div class="noimg"></div>'
        span = fmt_date(first["date"], False).split(" ", 1)[1] + (
            "" if first is latest else " – " + fmt_date(latest["date"], False).split(" ", 1)[1])
        return f"""<a class="card series" href="{rel}sections/{sslug(name)}/">{img}<div class="cardtext"><h3>{e(meta.get(name, {}).get('short', name))}</h3><p class="meta">{n} essay{'s' if n != 1 else ''} · {span}</p></div></a>"""

    for name, ps in by.items():
        s = meta.get(name, {})
        rel = "../../"
        desc = s.get("description", "")
        kids = children.get(name, [])
        sub = ""
        if kids:
            sub = '<h2 class="sect">Series in this section</h2><div class="grid">' + "".join(series_card(k, rel) for k in kids) + "</div>"
        parent = s.get("parent")
        crumbs = f'<a href="{rel}">Home</a> › <a href="{rel}sections/">Series</a>'
        if parent and parent in by:
            crumbs += f' › <a href="{rel}sections/{sslug(parent)}/">{e(meta.get(parent, {}).get("short", parent))}</a>'
        newest = s.get("order") == "newest"
        items = "".join(row(p, rel) for p in ps)
        pic = s.get("image") or ""
        lines = [x.strip() for x in desc.split("\n") if x.strip()]
        if lines and lines[0].lower().rstrip(":. ") in (name.lower(), s.get("short", "").lower()):
            lines = lines[1:]  # description repeats the series name as its first line
        paras = "".join(f"<p>{e(x)}</p>" for x in lines)
        art = f'<img class="landing-img" src="{e(cdn(pic, 600))}" alt="">' if pic else ""
        n = len(ps)
        toggle = "" if n < 3 else f"""<div class="order" role="group" aria-label="Order"><button data-o="old"{' aria-pressed="true"' if not newest else ''}>Oldest first</button><button data-o="new"{' aria-pressed="true"' if newest else ''}>Newest first</button></div>"""
        led = ledger_for.get(name)
        if led:
            paras += f'<p class="ledgerlink">Companion ledger: <a href="{rel}ledgers/{led["file"]}/">{e(led["title"])}</a></p>'
        body = f"""<p class="crumbs">{crumbs}</p>
<header class="landing">{art}<div><h1>{e(name)}</h1>{paras}
<p class="meta">{n} essay{'s' if n != 1 else ''} · <a href="{e(s.get('substack') or SUBSTACK + '/s/' + sslug(name))}">This series on Substack</a></p></div></header>
{sub}
<div class="listhead"><h2 class="sect">Essays</h2>{toggle}</div>
<ol class="rows" data-order="{'new' if newest else 'old'}">{items}</ol>
<script>
document.querySelectorAll('.order button').forEach(b => b.addEventListener('click', () => {{
  const ol = document.querySelector('ol.rows');
  if (ol.dataset.order !== b.dataset.o) {{ [...ol.children].reverse().forEach(li => ol.appendChild(li)); ol.dataset.order = b.dataset.o; }}
  document.querySelectorAll('.order button').forEach(x => x.setAttribute('aria-pressed', x === b));
}}));
</script>"""
        write(f"sections/{sslug(name)}/index.html", page(rel, f"{name} · {SITE_NAME}", body, desc[:300], active="Series"))

    # old (May 2026) series addresses: forward to their current page
    may_slugs = json.load(open(os.path.join(HERE, "may_slugs.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "may_slugs.json")) else {}
    for old, may_name in may_slugs.items():
        target = assign({"num": "", "title": may_name + ": x", "section": ""})
        if target == CATCH_ALL and may_name != CATCH_ALL or target not in by or sslug(target) == old:
            continue
        write(f"sections/{old}/index.html", f'<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../{sslug(target)}/"><link rel="canonical" href="../{sslug(target)}/"><a href="../{sslug(target)}/">{e(target)}</a>')

    # ---------- series index ----------
    top = [n for n in by if not meta.get(n, {}).get("parent") and n != CATCH_ALL]
    top.sort(key=lambda n: meta.get(n, {}).get("short", n).lower().removeprefix("the "))
    rel = "../"
    az = "".join(series_card(n, rel) for n in top)
    if CATCH_ALL in by:
        az += series_card(CATCH_ALL, rel)
    body = f"""<header class="serieshead"><h1>All series</h1><p class="meta">{len(by)} series and sections, A to Z. Grouped sections (The Middle Kingdom, The Opera Cycle, The AI Trials and Tribulations) open onto their own series.</p></header>
<div class="grid">{az}</div>"""
    write("sections/index.html", page(rel, f"All series · {SITE_NAME}", body, active="Series"))

    # ---------- ledgers index ----------
    items = []
    for l in ledgers:
        ser = l.get("series")
        ser_link = f' · <a href="../sections/{sslug(ser)}/">{e(meta.get(ser, {}).get("short", ser))}</a>' if ser in by else ""
        if l.get("file"):
            href, live = f'{l["file"]}/', f' · <a href="https://claude.ai/artifact/{l["slug"]}">Live version in Claude</a>'
        else:
            href, live = l["external"], ""
        items.append(f'<li><h3><a href="{e(href)}">{e(l["title"])}</a></h3><p>{e(l["about"])}</p><p class="meta">{ser_link.lstrip(" ·")}{live}</p></li>')
    body = f"""<header class="serieshead"><h1>Public ledgers</h1><p class="meta">The running records behind the series: what was undone, what can be repaired, and the draft bills offered from north of the border. Copies here are refreshed daily from the live versions.</p></header>
<ul class="ledgers">{''.join(items)}</ul>"""
    write("ledgers/index.html", page("../", f"Ledgers · {SITE_NAME}", body, active="Ledgers"))

    # ---------- chronological ----------
    months = OrderedDict()
    for p in sorted(posts, key=lambda p: p["date"], reverse=True):
        k, label = month_key(p["date"])
        months.setdefault((k, label), []).append(p)
    jump = " ".join(f'<a href="#m{k}">{label.split()[0][:3]} {label.split()[1][2:]}</a>' for (k, label) in months)
    blocks = []
    for (k, label), ps in months.items():
        lis = "".join(
            f'<li><time>{fmt_date(p["date"], False)}</time> <a href="../posts/{p["num"]}/">{e(p["title"])}</a> <span class="ser">{e(p["series_short"])}</span></li>'
            for p in ps)
        blocks.append(f'<section id="m{k}"><h2 class="sect">{label} <small>{len(ps)} essays</small></h2><ul class="chrono">{lis}</ul></section>')
    body = f"""<header class="serieshead"><h1>Every essay, by date</h1><p class="meta">{len(posts)} essays, newest first.</p><p class="jump">{jump}</p></header>{''.join(blocks)}"""
    write("chronological/index.html", page("../", f"By date · {SITE_NAME}", body, active="By date"))

    # ---------- search ----------
    body = """<header class="serieshead"><h1>Search the archive</h1><p class="meta">Searches the full text of every essay. Filter by series once results appear.</p></header>
<div id="search"></div>
<script src="../pagefind/pagefind-ui.js"></script>
<script>
window.addEventListener('DOMContentLoaded', () => {
  const ui = new PagefindUI({ element: "#search", showSubResults: true, showImages: true, pageSize: 10, resetStyles: false,
    translations: { placeholder: "Search 2,000+ essays" } });
  const q = new URLSearchParams(location.search).get('q');
  if (q) ui.triggerSearch(q);
});
</script>"""
    write("search/index.html", page("../", f"Search · {SITE_NAME}", body,
                                    extra_head='<link href="../pagefind/pagefind-ui.css" rel="stylesheet">', active="Search"))

    # ---------- home ----------
    rel = ""
    latest = sorted(posts, key=lambda p: p["date"], reverse=True)[:12]
    active_series = sorted(top, key=lambda n: max(p["date"] for p in by[n] + sum((by[c] for c in children.get(n, [])), [])), reverse=True)[:12]
    first_year = fmt_date(posts[0]["date"]).split(" ", 1)[1]
    body = f"""<section class="hero">
<h1>Every essay. Every series. One snowman.</h1>
<p class="tally">{len(posts):,} essays in {len(by)} series · updated daily</p>
<p>The complete writing of {AUTHOR} at CanadianSnowmanSays, since {first_year}: American political accountability, AI governance, geopolitics, history, satire and fiction.</p>
<form class="homesearch" action="search/" method="get"><input type="search" name="q" placeholder="Search every essay…" aria-label="Search"><button>Search</button></form>
</section>
<h2 class="sect">Latest essays <a class="more" href="chronological/">Everything by date →</a></h2>
<div class="grid">{''.join(card(p, rel) for p in latest)}</div>
<h2 class="sect">Public ledgers <a class="more" href="ledgers/">All ledgers →</a></h2>
<div class="ledgerstrip">{''.join(f'<a href="ledgers/{l["file"]}/">{e(l["title"])}</a>' for l in ledgers if l.get("file"))}</div>
<h2 class="sect">Recently active series <a class="more" href="sections/">All {len(by)} series →</a></h2>
<div class="grid">{''.join(series_card(n, rel) for n in active_series)}</div>"""
    write("index.html", page(rel, f"{SITE_NAME} · The Archive", body,
                             f"The complete archive of {AUTHOR}'s essays at CanadianSnowmanSays.", active="Home"))

    write("404.html", page("/canadiansnowman-archive/", f"Not found · {SITE_NAME}",
                           '<header class="serieshead"><h1>That page isn’t here</h1><p><a href="/canadiansnowman-archive/">Go to the archive’s front page</a> or <a href="/canadiansnowman-archive/search/">search</a>.</p></header>'))

    print(f"built {len(posts)} essays in {len(by)} series into {out}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "_site")

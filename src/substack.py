"""Read Stephen's public Substack archive (no login needed)."""
import json
import time
import urllib.parse
import urllib.request

PUB = "https://canadiansnowmansays.substack.com"
UA = "CanadianSnowmanArchive/1.0 (+https://canadiansnowmansays.github.io/canadiansnowman-archive/)"


def _get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # rate limits and blips: back off and retry
            if i == tries - 1 or getattr(e, "code", None) in (401, 403, 404):
                raise  # a refusal won't change on retry
            time.sleep(5 * (i + 1))
            print("retrying after", e)


def archive(stop_at=None, max_pages=1000, pub=None):
    """Yield published posts newest-first. Stops once a post id in stop_at is seen."""
    cursor = None
    for _ in range(max_pages):
        url = f"{pub or PUB}/api/v1/archive?sort=new"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor)
        d = _get(url)
        for p in d.get("posts", []):
            if stop_at and str(p["id"]) in stop_at:
                return
            yield p
        cursor = d.get("nextCursor")
        if not cursor or not d.get("posts"):
            return
        time.sleep(0.5)


def post(slug, pub=None):
    """One post with its full body_html."""
    return _get(f"{pub or PUB}/api/v1/posts/{urllib.parse.quote(slug)}")


def feed(pub=None):
    """The public RSS feed: the 20 most recent posts with full text (no ids or sections)."""
    import email.utils
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(f"{pub or PUB}/feed", headers={"User-Agent": UA})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=60).read())
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    out = []
    for it in root.iter("item"):
        link = it.findtext("link") or ""
        enc = it.find("enclosure")
        when = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        out.append({
            "slug": link.rstrip("/").rsplit("/p/", 1)[-1],
            "title": it.findtext("title") or "",
            "subtitle": it.findtext("description") or "",
            "post_date": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "body_html": it.findtext("content:encoded", namespaces=ns) or "",
            "cover_image": enc.get("url") if enc is not None else "",
        })
    return out

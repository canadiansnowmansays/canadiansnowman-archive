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
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))
            print("retrying after", e)


def archive(stop_at=None, max_pages=1000):
    """Yield published posts newest-first. Stops once a post id in stop_at is seen."""
    cursor = None
    for _ in range(max_pages):
        url = f"{PUB}/api/v1/archive?sort=new"
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


def post(slug):
    """One post with its full body_html."""
    return _get(f"{PUB}/api/v1/posts/{urllib.parse.quote(slug)}")

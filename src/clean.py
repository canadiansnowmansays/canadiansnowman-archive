"""Turn a Substack post body into clean, self-contained archive HTML.

Shared by the one-time import (import_export.py) and the daily update (update.py).
"""
import re
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup, Comment

CDN = "https://substackcdn.com/image/fetch/"


def cdn(src, width=1100, height=None, crop=False):
    """Resized copy of a Substack image, served from Substack's image CDN."""
    if not src:
        return ""
    m = re.match(r"https://substackcdn\.com/image/fetch/[^/]*/(https?.*)$", src)
    if m:  # already a CDN URL: unwrap to the original
        src = unquote(m.group(1))
    opts = f"w_{width}"
    if height:
        opts += f",h_{height}"
    opts += ",c_fill" if crop else ",c_limit"
    opts += ",f_auto,q_auto:good,fl_progressive:steep"
    return f"{CDN}{opts}/{quote(src, safe='')}"


def _best_src(img):
    src = img.get("src") or ""
    if "substack-post-media" in src or "substackcdn" in src or src.startswith("http"):
        return src
    return ""


def clean(body_html):
    """Return (clean_html, cover_src, word_count)."""
    soup = BeautifulSoup(body_html, "html.parser")

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Subscribe boxes, share/restack buttons, image "expand" icons, forms
    for sel in [
        "div.subscription-widget-wrap-editor",
        "div.subscription-widget-wrap",
        "div.image-link-expand",
        "form",
        "svg",
        "div.share-dialog",
    ]:
        for el in soup.select(sel):
            el.decompose()

    # Subscribe / share buttons (keep buttons that link elsewhere, as plain links)
    for bw in soup.select("p.button-wrapper, div.button-wrapper"):
        a = bw.find("a")
        if not a or not a.get("href") or re.search(r"/subscribe|/share|action=share", a["href"]):
            bw.decompose()
            continue
        p = soup.new_tag("p")
        link = soup.new_tag("a", href=a["href"])
        link.string = a.get_text(strip=True) or a["href"]
        p.append(link)
        bw.replace_with(p)

    # "Thanks for reading! Subscribe..." paragraphs left behind in older posts
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if re.match(r"^(Thanks for reading|Share$|Subscribe now$|Leave a comment$)", t, re.I) and len(t) < 160:
            p.decompose()

    cover = ""
    # Images: rebuild each figure as a plain <figure><img><figcaption>
    for fig in soup.select("div.captioned-image-container"):
        img = fig.find("img")
        cap = fig.find("figcaption")
        src = _best_src(img) if img else ""
        if not src:
            fig.decompose()
            continue
        if not cover:
            cover = src
        new = soup.new_tag("figure")
        alt = (img.get("alt") or "").strip() if img else ""
        new.append(soup.new_tag("img", src=cdn(src), alt=alt, loading="lazy", decoding="async"))
        if cap and cap.get_text(strip=True):
            fc = soup.new_tag("figcaption")
            for child in list(cap.children):
                fc.append(child)
            new.append(fc)
        fig.replace_with(new)

    # Any remaining bare images
    for img in soup.find_all("img"):
        if img.find_parent("figure") and img.get("loading") == "lazy":
            continue
        src = _best_src(img)
        if not src:
            img.decompose()
            continue
        if not cover:
            cover = src
        img.attrs = {"src": cdn(src), "alt": img.get("alt", ""), "loading": "lazy", "decoding": "async"}

    # Embedded video/tweets: keep a plain link so nothing depends on Substack scripts
    for wrap in soup.select("div.youtube-wrap, div.vimeo-wrap, div.spotify-wrap, div.soundcloud-wrap, div.twitter-embed"):
        url = ""
        attrs = wrap.get("data-attrs") or ""
        m = re.search(r'"videoId":"([^"]+)"', attrs)
        if m and "youtube" in " ".join(wrap.get("class", [])):
            url = f"https://www.youtube.com/watch?v={m.group(1)}"
        else:
            m = re.search(r'"url":"([^"]+)"', attrs)
            if m:
                url = m.group(1).replace("\\/", "/")
        if url:
            p = soup.new_tag("p", attrs={"class": "embed"})
            a = soup.new_tag("a", href=url)
            a.string = "Watch / view the embedded item"
            p.append(a)
            wrap.replace_with(p)
        else:
            wrap.decompose()

    # Strip Substack's attributes and wrappers we no longer need
    keep = {"href", "src", "alt", "loading", "decoding", "colspan", "rowspan", "id", "start"}
    for el in soup.find_all(True):
        if el.name == "a" and el.get("href"):
            el.attrs = {"href": el["href"]}
            continue
        el.attrs = {k: v for k, v in el.attrs.items() if k in keep or (k == "class" and el.name == "p" and v == ["embed"])}
    for el in soup.select("div, picture, source, span"):
        if el.name == "source":
            el.decompose()
        else:
            el.unwrap()
    for el in soup.find_all(["p", "h2", "h3", "h4"]):
        if not el.get_text(strip=True) and not el.find("img"):
            el.decompose()

    out = str(soup).strip()
    words = len(re.findall(r"\b\w[\w'’-]*\b", soup.get_text(" ")))
    return out, cover, words

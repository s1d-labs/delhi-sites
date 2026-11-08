"""Pure functions: which links to follow, and what a page says. Tested on saved pages."""
import hashlib
import html
import re
from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlsplit, urlunsplit

DOC = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "csv", "zip", "rar", "7z", "kml", "kmz", "geojson", "shp", "txt", "rtf", "xml", "json"}
MEDIA = {"jpg", "jpeg", "png", "gif", "svg", "webp", "ico", "bmp", "tif", "tiff", "mp4", "mp3", "avi", "wav", "webm", "mov", "css", "js", "woff", "woff2", "ttf", "eot", "map"}
# links that repeat a page for ever or that are actions, not content
TRAP = re.compile(r"//online\.ndmc\.gov\.in/(?!rti/)|/wp-json/|/author/|/blog/page/|[?&]p=\d|/(calendar|login|logout|signin|signup|register|user/|admin|wp-admin|print|share|feed|cart|captcha)\b|[?&](print|share|sort|order|lang|replytocom|destination|ical|date|month|year)=|mailto:|tel:|javascript:", re.I)
DROP_QUERY = re.compile(r"^(utm_.*|fbclid|gclid|sessionid|sid|phpsessid|jsessionid|ref|from)$", re.I)
TAGS = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>|<!--.*?-->", re.I | re.S)
HREF = re.compile(r"""<(?:a|area|iframe|embed|object|link)\b[^>]*?\b(?:href|src|data)\s*=\s*["']?([^"'\s>]+)""", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def key_of(url):
    return hashlib.sha1(url.encode()).hexdigest()[:24]


def same_site(host, site):
    h, s = host.lower().removeprefix("www."), site.lower().removeprefix("www.")
    return h == s or h.endswith("." + s)


def clean(url, base=""):
    """One spelling for one address: no fragment, no tracking fields, sorted query."""
    url = html.unescape(url.strip())
    url = urldefrag(urljoin(base, url))[0]
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return ""
    q = urlencode(sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not DROP_QUERY.match(k)))
    return urlunsplit(("https", u.netloc.lower(), re.sub(r"/{2,}", "/", u.path) or "/", q, ""))


def kind(url):
    ext = urlsplit(url).path.rsplit("/", 1)[-1].rpartition(".")[2].lower()
    return "doc" if ext in DOC else "skip" if ext in MEDIA else "page"


def invented(url):
    """Addresses a server answers whatever the path says: bas.aspx/a/b/c, or a/b/a/b/a/b from relative links."""
    p = urlsplit(url).path
    parts = [x.lower() for x in p.split("/") if x]
    return bool(re.search(r"\.aspx?/", p, re.I)) or len(parts) > 12 or any(parts.count(x) >= 3 for x in set(parts))


def links(page, base, site):
    """Addresses on this site that a crawl should visit next, in page order, once each."""
    seen, out = set(), []
    for m in HREF.findall(TAGS.sub(" ", page)):
        u = clean(m, base)
        if not u or u in seen or TRAP.search(u) or invented(u) or not same_site(urlsplit(u).hostname, site) or kind(u) == "skip":
            continue
        seen.add(u)
        out.append(u)
    return out


def read(page):
    """Title and plain text of an HTML page."""
    t = TITLE.search(page)
    body = TAGS.sub(" ", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?i)</(p|div|li|tr|h\d|td|th)>|<br\s*/?>", "\n", body)))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return (html.unescape(re.sub(r"\s+", " ", t.group(1))).strip()[:300] if t else ""), text

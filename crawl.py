"""Crawl one site. A queue item is one address. A page gives one record, its raw HTML in the bucket and new queue items. A document goes to
the bucket with one record. Every record id is the address's hash, so a rerun replaces, never doubles."""
import collections
import gzip
import hashlib
import os
import signal
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import certifi
import requests

from scrape_hub_client import HubClient, seed_queue

from sitecrawl import clean, key_of, kind, links, read, same_site

PROJECT = os.environ["SCRAPE_POOL_PROJECT"]
SITE = os.environ["SITE"]
DEADLINE = time.time() + float(os.environ.get("SCRAPE_MAX_HOURS", "1")) * 3600 - 120
MAX_DEPTH = 12
MAX_BYTES = 200 * 1024 * 1024
TEXT_CAP = 150_000
PER_PATH = 2000             # query-string variants of one path: a search or list page must not fill the queue
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; s1d-labs public records crawl; +https://labs.s1d.me)"}
stop = False


def on_signal(*_):
    global stop
    stop = True


def fetch(hub, s, url):
    t = time.time()
    try:
        r = s.get(url, timeout=(20, 120), stream=True, allow_redirects=True)
        body = b""
        for chunk in r.iter_content(1 << 16):
            body += chunk
            if len(body) > MAX_BYTES:
                hub.failure("too-big", url, f"over {MAX_BYTES} bytes")
                r.close()
                return None, None
    except requests.RequestException as e:
        hub.metric("http_error")
        hub.error()
        hub.failure("no-answer", url, type(e).__name__)
        return None, None
    hub.metric("n_http")
    hub.metric("t_http_s", time.time() - t)
    if r.status_code != 200:
        hub.metric(f"http_{r.status_code}")
        if r.status_code in (403, 429, 503):
            hub.block()
        if r.status_code in (404, 410):
            return "gone", None
        return None, None
    return r, body


def decode(body, declared):
    """The body is already read, so the charset must come from these bytes: requests.apparent_encoding would read the response again."""
    if declared and declared.lower() != "iso-8859-1":
        try:
            return body.decode(declared)
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1", "replace")


def ext_of(url, ctype):
    e = urlsplit(url).path.rsplit("/", 1)[-1].rpartition(".")[2].lower()
    if 1 <= len(e) <= 5 and e.isalnum():
        return e
    return {"application/pdf": "pdf", "text/csv": "csv", "application/zip": "zip"}.get(ctype, "bin")


def trust():
    """certifi plus the public intermediates in certs/ that some sites fail to send. Verification stays on."""
    extra = sorted(Path(__file__).parent.glob("certs/*.pem"))
    if not extra:
        return True
    with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as f:
        for p in [Path(certifi.where())] + extra:
            f.write(p.read_bytes() + b"\n")
    return f.name


def main():
    hub = HubClient(PROJECT, job_index=int(os.environ.get("SCRAPE_JOB_INDEX", 0)), total_jobs=int(os.environ.get("SCRAPE_TOTAL_JOBS", 1)))
    s = requests.Session()
    s.verify = trust()
    s.headers.update(HEADERS)
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    paths = collections.Counter()
    seen, fresh = set(), []

    def send():
        if fresh:
            seed_queue(PROJECT, fresh)
            fresh.clear()

    def work(item, url, depth):
        r, body = fetch(hub, s, url)
        if r == "gone":
            hub.complete([item["key"]], "done", fetched=0)
            return
        if r is None:
            hub.complete([item["key"]], "failed", error="no page")
            return
        final = clean(r.url) or url
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        rid = key_of(url)
        sha = hashlib.sha256(body).hexdigest()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if "html" in ctype and kind(url) == "page":
            page = decode(body, r.encoding)
            title, text = read(page)
            got = links(page, final, SITE)
            path = f"pages/{rid}.html.gz"
            hub.upload_many([(path, gzip.compress(body), "application/gzip")])
            hub.record(rid, {"type": "page", "url": url, "final_url": final, "title": title, "text": text[:TEXT_CAP], "text_len": len(text), "links": len(got), "file": path, "sha256": sha, "fetched_at": now, "depth": depth, "last_modified": r.headers.get("last-modified", "")})
            if depth < MAX_DEPTH:
                for u in got:
                    k = key_of(u)
                    p = urlsplit(u)
                    paths[p.path] += 1
                    if k in seen or (p.query and paths[p.path] > PER_PATH):
                        continue
                    seen.add(k)
                    fresh.append({"key": k, "payload": {"url": u, "depth": depth + 1}})
                if len(fresh) >= 200:
                    send()
        elif same_site(urlsplit(final).hostname or "", SITE) or kind(url) == "doc":
            e = ext_of(url, ctype)
            path = f"docs/{sha[:2]}/{sha}.{e}"
            hub.upload_many([(path, body, ctype or "application/octet-stream")])
            hub.record(rid, {"type": "document", "url": url, "final_url": final, "name": urlsplit(url).path.rsplit("/", 1)[-1][:200], "content_type": ctype, "bytes": len(body), "file": path, "sha256": sha, "fetched_at": now, "last_modified": r.headers.get("last-modified", "")})
        hub.complete([item["key"]], "done", fetched=1)

    try:
        while time.time() < DEADLINE and not stop:
            if hub.settings.get("paused"):
                time.sleep(30)
                continue
            items = hub.claim(1, steal=True, retry_failed=True)
            if not items:
                break
            item = items[0]
            url, depth = item["payload"]["url"], item["payload"].get("depth", 0)
            try:
                work(item, url, depth)
            except Exception as e:      # one bad page must not stop the crawl
                hub.failure("bad-page", url, f"{type(e).__name__}: {e}"[:200])
                hub.complete([item["key"]], "failed", error=type(e).__name__)
            time.sleep(max(.5, hub.settings.get("delay_ms", 0) / 1000))
        send()
        hub.close("finished" if not stop else "failed", "" if not stop else "stopped by signal")
    except Exception as e:
        send()
        hub.close("failed", str(e)[:200])
        raise


if __name__ == "__main__":
    sys.exit(main())

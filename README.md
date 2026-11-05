# delhi-sites: every public page and document of Delhi agency websites

A family of the s1d-labs scrape pool. One project per site (`family.py`). The queue starts at the home page and grows as the crawl finds new
links on the same site.

| Stored | Where |
|---|---|
| Page: address, title, plain text, link count | one record per address, HTML in `pages/<id>.html.gz` in the bucket |
| Document (PDF, Word, Excel, KML, ZIP and others): address, name, size, SHA-256 | one record per address, the file in `docs/<sha>` in the bucket |

- The sites answer from India, so the projects use `geo="IN"`: India pool servers only.
- Pace: 2 workers per site, 1 request per second per worker. The Urban Development site has 1 worker and 1 request every 2 seconds. The hub's back-off applies.
- No login, captcha or OTP is passed. Search forms are not filled. TLS checks stay on.
- Photos, video, style sheets and scripts are not stored.

Setup: change `family.py`, then Actions -> setup. Tests: `python -m pytest tests`.

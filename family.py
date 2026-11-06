"""What this family scrapes: every public page and document on the websites of Delhi agencies.

One project per site, on the pool's India servers (geo="IN"). The queue starts at the home page and grows: crawl.py adds each new link it
finds on the same site. Sites with a login, a captcha or a search form behind them are crawled only as far as plain links go.
"""
import json
from pathlib import Path

from sitecrawl import key_of

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]

# slug, host, title, text that the home page always holds (for the health check)
SITES = [
    ("delhi", "delhi.gov.in", "Government of NCT of Delhi", "delhi"),
    ("finance", "finance.delhi.gov.in", "Delhi Finance Department", "finance"),
    ("ifc", "ifc.delhi.gov.in", "Delhi Irrigation and Flood Control", "flood"),
    ("djb", "delhijalboard.delhi.gov.in", "Delhi Jal Board", "jal board"),
    ("transport", "transport.delhi.gov.in", "Delhi Transport Department", "transport"),
    ("ceo", "ceodelhi.gov.in", "Chief Electoral Officer, Delhi", "election"),
    ("sec", "sec.delhi.gov.in", "State Election Commission, Delhi", "election"),
    ("lokayukta", "lokayukta.delhi.gov.in", "Delhi Lokayukta", "lokayukta"),
    ("vigilance", "vigilance.delhi.gov.in", "Delhi Directorate of Vigilance", "vigilance"),
    ("home", "home.delhi.gov.in", "Delhi Home Department", "home"),
    ("traffic", "traffic.delhipolice.gov.in", "Delhi Traffic Police", "traffic"),
    ("police", "delhipolice.gov.in", "Delhi Police", "police"),
    ("ndmc", "www.ndmc.gov.in", "New Delhi Municipal Council", "ndmc"),
    ("tourism", "delhitourism.gov.in", "Delhi Tourism", "delhi"),
    ("assembly", "delhiassembly.delhi.gov.in", "Delhi Legislative Assembly", "assembly"),
    ("highcourt", "delhihighcourt.nic.in", "Delhi High Court public pages", "high court"),
    ("morth", "morth.gov.in", "Ministry of Road Transport and Highways", "road"),
    ("mcd", "mcdonline.nic.in", "Municipal Corporation of Delhi", "portal"),
    ("udd", "udd.delhi.gov.in", "Delhi Urban Development Department, with MLA fund orders", "urban"),
    ("uttipec", "uttipec.org.in", "UTTIPEC, DDA road design body", "uttipec"),
    ("dsiidc", "dsiidc.delhi.gov.in", "Delhi State Industrial and Infrastructure Development Corporation", "dsiidc"),
]
# the MLA fund orders (MLALAD), listed by year on pages that a plain link crawl does not reach
UDD_ORDERS = [u for u in (Path(__file__).parent / "udd_orders.txt").read_text().split("\n") if u]

PROJECTS = [
    {
        "name": f"{FAMILY}-{slug}",
        "title": title,
        "task": "crawl",
        "target": host,
        "env": {"SITE": host},
        "probe": f"{FAMILY}:{host}",
        "unit_label": "url", "record_label": "page or document",
        "items": [{"key": "start", "payload": {"url": f"https://{host}/portal" if slug == "mcd" else f"https://{host}/", "depth": 0}}] + ([{"key": key_of(u), "payload": {"url": u, "depth": 12}} for u in UDD_ORDERS] if slug == "udd" else []),
        "workers": 2,
        "delay_ms": 2000 if slug == "udd" else 1000,
    }
    for slug, host, title, _ in SITES
]

PROBES = [{"name": f"{FAMILY}:{host}", "url": f"https://{host}/", "expect": text} for _, host, _, text in SITES]

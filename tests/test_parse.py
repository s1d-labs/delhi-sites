from pathlib import Path

from sitecrawl import clean, kind, links, read, same_site

PAGE = (Path(__file__).parent / "pages/sample.html").read_text()


def test_links():
    got = links(PAGE, "https://example.delhi.gov.in/works/", "example.delhi.gov.in")
    assert got == ["https://example.delhi.gov.in/a/b.pdf", "https://example.delhi.gov.in/works/list?page=2", "https://example.delhi.gov.in/viewer/report.pdf"]


def test_read():
    title, text = read(PAGE)
    assert title == "Road & Works"
    assert "Line one." in text and "var a" not in text


def test_clean():
    assert clean("HTTP://x.gov.in//a//b?z=1&a=2&utm_medium=q#f".replace("HTTP", "http")) == "https://x.gov.in/a/b?a=2&z=1"
    assert clean("mailto:a@b") == ""


def test_kind():
    assert kind("https://x/a.PDF") == "doc" and kind("https://x/a.png") == "skip" and kind("https://x/a") == "page"


def test_same_site():
    assert same_site("www.ndmc.gov.in", "ndmc.gov.in") and same_site("a.ndmc.gov.in", "www.ndmc.gov.in") and not same_site("x.gov.in", "ndmc.gov.in")

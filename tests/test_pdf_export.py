"""Tests for PDF export discoverability: a "Download as PDF" link that opens
/book and auto-triggers the browser's print-to-PDF dialog (no new
dependency — see FEATURES.md's "no new dependencies" rule and the /book
print stylesheet already built for F10)."""

from datetime import date

from app import storage


def test_timeline_links_to_book_pdf_with_print_param(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'href="/book?print=1"' in html
    assert "Download as PDF" in html


def test_book_page_loads_normally_with_print_param(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    resp = auth_client.get("/book?print=1")
    assert resp.status_code == 200
    assert b"js/book.js" in resp.data

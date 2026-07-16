"""Tests for FEATURES.md F10: the book view (/book)."""

from datetime import date

from app import storage


def test_book_requires_auth(client):
    resp = client.get("/book")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_book_contains_all_readable_stories_in_order(auth_client, stories_dir):
    id1 = storage.create_story(stories_dir, "First story", date(2024, 1, 1), "Body one")
    storage.create_story(stories_dir, "Second story", date(2025, 6, 1), "Body two")

    resp = auth_client.get("/book")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert html.index("First story") < html.index("Second story")
    assert "Body one" in html
    assert "Body two" in html
    assert f'href="/story/{id1}"' not in html  # book renders inline, not links to stories


def test_book_excludes_drafts_and_sealed(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2024, 1, 1), "visible")
    storage.create_story(stories_dir, "A draft", date(2024, 2, 1), "draft body", draft=True)
    storage.create_story(
        stories_dir, "A sealed letter", date(2024, 3, 1), "secret body", unlock=date(2040, 1, 1)
    )

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "Published" in html
    assert "A draft" not in html
    assert "draft body" not in html
    assert "A sealed letter" not in html
    assert "secret body" not in html


def test_book_cover_shows_title_and_year_range(auth_client, stories_dir):
    storage.create_story(stories_dir, "Early", date(2022, 1, 1), "")
    storage.create_story(stories_dir, "Late", date(2025, 1, 1), "")

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "book-cover__title" in html
    assert "Storybook" in html
    assert "Stories from 2022 to 2025" in html


def test_book_cover_single_year_range(auth_client, stories_dir):
    storage.create_story(stories_dir, "Only", date(2024, 5, 1), "")
    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "Stories from 2024" in html
    assert "to 2024" not in html


def test_book_empty_state_shows_no_range(auth_client):
    resp = auth_client.get("/book")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Stories from" not in html


def test_book_shows_authors_when_configured(auth_client, stories_dir, app):
    app.config["AUTHORS"] = [{"name": "Papa", "color": "#d9a441"}]
    storage.create_story(stories_dir, "Story", date(2024, 1, 1), "", author="Papa")

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "book-cover__authors" in html
    assert "Papa" in html


def test_book_ornament_between_stories_not_after_last(auth_client, stories_dir):
    storage.create_story(stories_dir, "First", date(2024, 1, 1), "")
    storage.create_story(stories_dir, "Second", date(2024, 2, 1), "")

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert html.count("book__ornament") == 1


def test_book_print_button_present(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2024, 1, 1), "")
    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "book__print-btn" in html
    assert "js/book.js" in html


def test_timeline_links_to_book(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2024, 1, 1), "")
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'href="/book"' in html
    assert "Read as a book" in html


def test_story_page_rendering_unaffected_by_shared_partial(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "A test story", date(2024, 3, 5),
        "This has ==a highlight== and an image.\n\n![A caption](photo-001.jpg)",
    )
    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "<mark>a highlight</mark>" in html
    assert f"/story/{story_id}/media/photo-001.jpg" in html
    assert "<figcaption>A caption</figcaption>" in html
    assert "story__footer" in html

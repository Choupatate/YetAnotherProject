"""Tests for FEATURES.md F16: writing prompts ("Graines d'histoires")."""

from app import prompts


def test_load_prompts_default_has_56_lines(stories_dir):
    result = prompts.load_prompts(stories_dir)
    assert len(result) == 56
    assert all(isinstance(p, str) and p for p in result)


def test_load_prompts_default_matches_shipped_file():
    default_text = prompts.DEFAULT_PROMPTS_PATH.read_text(encoding="utf-8")
    expected = [line.strip() for line in default_text.splitlines() if line.strip()]
    assert expected[0] == "Qu'est-ce qui t'a fait rire aux éclats cette semaine ?"
    assert len(expected) == 56


def test_load_prompts_override_replaces_default_entirely(stories_dir):
    (stories_dir / "prompts.txt").write_text(
        "Custom prompt one\nCustom prompt two\n", encoding="utf-8"
    )
    result = prompts.load_prompts(stories_dir)
    assert result == ["Custom prompt one", "Custom prompt two"]


def test_load_prompts_override_skips_comments_and_blank_lines(stories_dir):
    (stories_dir / "prompts.txt").write_text(
        "# a comment\n\nReal prompt\n   \n# another comment\nAnother real prompt\n",
        encoding="utf-8",
    )
    result = prompts.load_prompts(stories_dir)
    assert result == ["Real prompt", "Another real prompt"]


def test_load_prompts_override_strips_whitespace(stories_dir):
    (stories_dir / "prompts.txt").write_text("  Padded prompt   \n", encoding="utf-8")
    result = prompts.load_prompts(stories_dir)
    assert result == ["Padded prompt"]


def test_load_prompts_empty_override_falls_back_to_default(stories_dir):
    (stories_dir / "prompts.txt").write_text("\n\n# only comments\n", encoding="utf-8")
    result = prompts.load_prompts(stories_dir)
    assert len(result) == 56


def test_load_prompts_missing_override_uses_default(stories_dir):
    result = prompts.load_prompts(stories_dir)
    assert len(result) == 56


# --- editor page ---------------------------------------------------------------


def test_new_page_contains_a_prompt(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'id="editor-prompt"' in html
    assert 'id="editor-prompt-cycle"' in html
    assert 'aria-label="Another idea"' in html
    assert 'id="editor-prompts-data"' in html


def test_edit_page_does_not_contain_a_prompt(auth_client, stories_dir):
    from datetime import date

    from app import storage

    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    assert 'id="editor-prompt"' not in html


def test_new_page_hides_prompt_when_override_is_empty(auth_client, stories_dir, monkeypatch):
    monkeypatch.setattr(prompts, "DEFAULT_PROMPTS_PATH", stories_dir / "nonexistent.txt")
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'id="editor-prompt"' not in html

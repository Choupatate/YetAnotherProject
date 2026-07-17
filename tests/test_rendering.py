from app.rendering import render_markdown


def test_highlight_renders_as_mark():
    html = render_markdown("This is ==important==.", "/story/2026-01-01-story/media")
    assert "<mark>important</mark>" in html


def test_lone_image_wrapped_in_figure_with_caption():
    html = render_markdown("![The big moment](photo-001.jpg)", "/story/2026-01-01-story/media")
    assert "<figure>" in html
    assert 'src="/story/2026-01-01-story/media/photo-001.jpg"' in html
    assert "<figcaption>The big moment</figcaption>" in html


def test_image_without_alt_has_no_figcaption():
    html = render_markdown("![](photo-002.jpg)", "/story/2026-01-01-story/media")
    assert "<figure>" in html
    assert "<figcaption>" not in html


def test_absolute_image_src_not_rewritten():
    html = render_markdown("![alt](https://example.com/photo.jpg)", "/story/2026-01-01-story/media")
    assert 'src="https://example.com/photo.jpg"' in html


def test_tables_and_lists_extensions_work():
    html = render_markdown("- one\n- two\n", "/story/2026-01-01-story/media")
    assert "<li>one</li>" in html
    assert "<li>two</li>" in html


def test_basic_paragraph_and_emphasis():
    html = render_markdown("Hello *world*.", "/story/2026-01-01-story/media")
    assert "<em>world</em>" in html


def test_repeated_calls_do_not_leak_media_base_or_parse_state():
    """render_markdown reuses one Markdown parser per thread (perf); each
    call must still be fully independent of the last."""
    first = render_markdown("![a](photo-001.jpg)", "/story/one/media")
    second = render_markdown("![b](photo-002.jpg)", "/people/two/media")
    third = render_markdown("Hello *world*.", "/story/one/media")

    assert 'src="/story/one/media/photo-001.jpg"' in first
    assert 'src="/people/two/media/photo-002.jpg"' in second
    assert "/story/one/media" not in second
    assert "<em>world</em>" in third
    assert "<figure>" not in third

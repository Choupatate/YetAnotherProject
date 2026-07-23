from datetime import date

import pytest

from app import storage


def test_create_story_creates_folder_and_index(stories_dir):
    story_id = storage.create_story(stories_dir, "First bike ride", date(2026, 7, 14), "Hello **world**")
    assert story_id == "2026-07-14-first-bike-ride"
    assert (stories_dir / story_id / "index.md").is_file()

    story = storage.get_story(stories_dir, story_id)
    assert story.title == "First bike ride"
    assert story.date == date(2026, 7, 14)
    assert "Hello **world**" in story.body
    assert story.created is not None
    assert story.updated is not None


def test_create_story_slug_collision_appends_suffix(stories_dir):
    id1 = storage.create_story(stories_dir, "Same Title", date(2026, 1, 1), "one")
    id2 = storage.create_story(stories_dir, "Same Title", date(2026, 1, 1), "two")
    id3 = storage.create_story(stories_dir, "Same Title", date(2026, 1, 1), "three")

    assert id1 == "2026-01-01-same-title"
    assert id2 == "2026-01-01-same-title-2"
    assert id3 == "2026-01-01-same-title-3"


def test_list_stories_sorted_by_date_ascending(stories_dir):
    storage.create_story(stories_dir, "Later", date(2026, 6, 1), "")
    storage.create_story(stories_dir, "Earlier", date(2025, 1, 1), "")
    storage.create_story(stories_dir, "Middle", date(2025, 12, 31), "")

    stories = storage.list_stories(stories_dir)
    assert [s.title for s in stories] == ["Earlier", "Middle", "Later"]


def test_list_stories_does_not_include_body(stories_dir):
    storage.create_story(stories_dir, "Some story", date(2026, 1, 1), "secret body text")
    stories = storage.list_stories(stories_dir)
    assert stories[0].body is None


def test_list_stories_skips_malformed_folder(stories_dir, caplog):
    good_id = storage.create_story(stories_dir, "Good story", date(2026, 1, 1), "")

    bad_dir = stories_dir / "2026-01-02-bad-story"
    bad_dir.mkdir()
    (bad_dir / "index.md").write_text("not valid frontmatter at all: [", encoding="utf-8")

    stories = storage.list_stories(stories_dir)
    assert [s.id for s in stories] == [good_id]


def test_list_stories_empty_dir_returns_empty_list(stories_dir):
    assert storage.list_stories(stories_dir) == []


def test_get_story_returns_none_for_missing(stories_dir):
    assert storage.get_story(stories_dir, "2026-01-01-nope") is None


def test_get_story_rejects_invalid_id(stories_dir):
    assert storage.get_story(stories_dir, "../etc/passwd") is None
    assert storage.get_story(stories_dir, "Has Spaces") is None


def test_create_story_writes_atomically_leaving_no_tmp_file(stories_dir):
    story_id = storage.create_story(stories_dir, "Atomic write", date(2026, 1, 1), "body")
    story_dir = stories_dir / story_id
    assert (story_dir / "index.md").is_file()
    assert not list(story_dir.glob("*.tmp"))


def test_list_stories_ignores_stray_tmp_file(stories_dir):
    good_id = storage.create_story(stories_dir, "Good story", date(2026, 1, 1), "")
    (stories_dir / good_id / "index.md.tmp").write_text("garbage", encoding="utf-8")

    stories = storage.list_stories(stories_dir)
    assert [s.id for s in stories] == [good_id]


def test_save_story_updates_content_and_keeps_id(stories_dir):
    story_id = storage.create_story(stories_dir, "Original title", date(2026, 1, 1), "original body")
    storage.save_story(stories_dir, story_id, "New title", date(2026, 2, 2), "new body")

    story = storage.get_story(stories_dir, story_id)
    assert story.id == story_id
    assert story.title == "New title"
    assert story.date == date(2026, 2, 2)
    assert story.body.strip() == "new body"


def test_save_story_missing_raises(stories_dir):
    with pytest.raises(FileNotFoundError):
        storage.save_story(stories_dir, "2026-01-01-missing", "T", date(2026, 1, 1), "b")


def test_save_story_invalid_id_raises(stories_dir):
    with pytest.raises(storage.InvalidStoryId):
        storage.save_story(stories_dir, "../nope", "T", date(2026, 1, 1), "b")


def test_create_story_round_trips_people_tags_sources(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Beach day", date(2026, 1, 1), "body",
        people=["grandma", "uncle-jean"], tags=["beach", "summer"],
        sources=[{"url": "https://example.com/photo", "note": "from aunt Jane"}],
    )
    story = storage.get_story(stories_dir, story_id)
    assert story.people == ["grandma", "uncle-jean"]
    assert story.tags == ["beach", "summer"]
    assert story.sources == [{"url": "https://example.com/photo", "note": "from aunt Jane"}]


def test_new_story_defaults_people_tags_sources_to_empty_list(stories_dir):
    story_id = storage.create_story(stories_dir, "Plain story", date(2026, 1, 1), "body")
    story = storage.get_story(stories_dir, story_id)
    assert story.people == []
    assert story.tags == []
    assert story.sources == []


def test_save_story_none_leaves_people_tags_sources_unchanged(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body",
        people=["grandma"], tags=["beach"], sources=[{"url": "https://example.com", "note": ""}],
    )
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "new body")

    story = storage.get_story(stories_dir, story_id)
    assert story.people == ["grandma"]
    assert story.tags == ["beach"]
    assert story.sources == [{"url": "https://example.com", "note": ""}]


def test_save_story_empty_list_clears_people_tags_sources(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body",
        people=["grandma"], tags=["beach"], sources=[{"url": "https://example.com", "note": ""}],
    )
    storage.save_story(
        stories_dir, story_id, "Story", date(2026, 1, 1), "new body",
        people=[], tags=[], sources=[],
    )

    story = storage.get_story(stories_dir, story_id)
    assert story.people == []
    assert story.tags == []
    assert story.sources == []


def test_stories_featuring_returns_only_matching_stories(stories_dir):
    id1 = storage.create_story(stories_dir, "With grandma", date(2026, 1, 1), "", people=["grandma"])
    storage.create_story(stories_dir, "Without grandma", date(2026, 1, 2), "")

    featured = storage.stories_featuring(stories_dir, "grandma")
    assert [s.id for s in featured] == [id1]


# --- milestone / register of firsts (FEATURES.md F28) ------------------------


def test_create_story_with_milestone(stories_dir):
    story_id = storage.create_story(
        stories_dir, "First steps", date(2026, 1, 1), "body", milestone="First steps"
    )
    story = storage.get_story(stories_dir, story_id)
    assert story.milestone == "First steps"


def test_new_story_defaults_milestone_to_none(stories_dir):
    story_id = storage.create_story(stories_dir, "Plain story", date(2026, 1, 1), "body")
    assert storage.get_story(stories_dir, story_id).milestone is None


def test_save_story_milestone_none_leaves_unchanged(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", milestone="First steps"
    )
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "new body")
    assert storage.get_story(stories_dir, story_id).milestone == "First steps"


def test_save_story_milestone_empty_string_clears(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", milestone="First steps"
    )
    storage.save_story(
        stories_dir, story_id, "Story", date(2026, 1, 1), "new body", milestone=""
    )
    assert storage.get_story(stories_dir, story_id).milestone is None


def test_milestone_truncated_to_max_length(stories_dir):
    long_milestone = "x" * 200
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", milestone=long_milestone
    )
    story = storage.get_story(stories_dir, story_id)
    assert len(story.milestone) == storage.MAX_MILESTONE_LENGTH


def test_stories_with_milestones_returns_only_matching_readable_stories(stories_dir):
    storage.create_story(stories_dir, "First steps", date(2026, 3, 1), "", milestone="First steps")
    storage.create_story(stories_dir, "No milestone", date(2026, 1, 1), "")
    storage.create_story(
        stories_dir, "Draft first", date(2026, 2, 1), "", milestone="Draft", draft=True
    )
    all_stories = storage.list_stories(stories_dir)
    result = storage.stories_with_milestones(all_stories)
    assert [s.title for s in result] == ["First steps"]


def test_stories_with_milestones_sorted_chronologically(stories_dir):
    storage.create_story(stories_dir, "Second first", date(2026, 6, 1), "", milestone="Second")
    storage.create_story(stories_dir, "First first", date(2026, 1, 1), "", milestone="First")
    all_stories = storage.list_stories(stories_dir)
    result = storage.stories_with_milestones(all_stories)
    assert [s.title for s in result] == ["First first", "Second first"]


# --- growth_photos: the birthday photo wall (FEATURES.md F29) ----------------


def _story_with_cover(id_, story_date, cover="photo-001.jpg"):
    return storage.Story(
        id=id_, title=id_, date=story_date, created=None, updated=None, cover=cover
    )


def test_growth_photos_empty_when_no_covers():
    result = storage.growth_photos([], date(2020, 6, 18), today=date(2023, 1, 1))
    assert result == []


def test_growth_photos_one_entry_per_birthday():
    birthdate = date(2020, 6, 18)
    stories = [
        _story_with_cover("newborn", date(2020, 6, 20)),
        _story_with_cover("age1", date(2021, 6, 15)),
    ]
    result = storage.growth_photos(stories, birthdate, today=date(2022, 1, 1))
    assert [e["age"] for e in result] == [0, 1]
    assert result[0]["story"].id == "newborn"
    assert result[1]["story"].id == "age1"


def test_growth_photos_picks_nearest_photo_overall():
    birthdate = date(2020, 6, 18)
    stories = [
        _story_with_cover("far", date(2020, 1, 1)),
        _story_with_cover("near", date(2020, 6, 19)),
    ]
    result = storage.growth_photos(stories, birthdate, today=date(2020, 12, 1))
    assert result[0]["story"].id == "near"


def test_growth_photos_stops_before_future_birthdays():
    birthdate = date(2020, 6, 18)
    stories = [_story_with_cover("only", date(2020, 6, 20))]
    result = storage.growth_photos(stories, birthdate, today=date(2022, 1, 1))
    assert [e["age"] for e in result] == [0, 1]


def test_growth_photos_feb29_birthdate_uses_mar1_makeup():
    birthdate = date(2020, 2, 29)
    stories = [_story_with_cover("only", date(2021, 3, 1))]
    result = storage.growth_photos(stories, birthdate, today=date(2021, 3, 1))
    assert [e["birthday"] for e in result] == [date(2020, 2, 29), date(2021, 3, 1)]


def test_growth_photos_excludes_stories_without_covers():
    birthdate = date(2020, 6, 18)
    stories = [
        storage.Story(id="no-cover", title="x", date=date(2020, 6, 18), created=None, updated=None),
    ]
    result = storage.growth_photos(stories, birthdate, today=date(2020, 7, 1))
    assert result == []


def test_growth_photos_excludes_drafts_and_sealed():
    birthdate = date(2020, 6, 18)
    draft = storage.Story(
        id="draft", title="x", date=date(2020, 6, 18), created=None, updated=None,
        cover="c.jpg", draft=True,
    )
    result = storage.growth_photos([draft], birthdate, today=date(2020, 7, 1))
    assert result == []


def test_path_safety_story_id_regex():
    assert storage.is_valid_story_id("2026-07-14-first-bike-ride")
    assert not storage.is_valid_story_id("../etc/passwd")
    assert not storage.is_valid_story_id("Has Spaces")
    assert not storage.is_valid_story_id("")
    assert not storage.is_valid_story_id("UPPER-case")


def test_path_safety_filename_regex():
    assert storage.is_valid_filename("photo-001.jpg")
    assert not storage.is_valid_filename("../../etc/passwd")
    assert not storage.is_valid_filename("photo 001.jpg")
    assert not storage.is_valid_filename("")


def test_thumb_filename_round_trips():
    assert storage.thumb_filename("photo-001.jpg") == "photo-001.thumb.jpg"
    assert storage.thumb_filename("photo-002.png") == "photo-002.thumb.png"
    assert storage.original_filename_from_thumb("photo-001.thumb.jpg") == "photo-001.jpg"
    assert storage.original_filename_from_thumb("photo-001.jpg") is None


def test_slugify_lowercases_ascii_and_truncates():
    assert storage.slugify("Hello, World!") == "hello-world"
    long_title = "A" * 100
    assert len(storage.slugify(long_title)) <= 60


def test_save_image_resizes_and_names_sequentially(stories_dir, jpeg_bytes):
    from PIL import Image
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(stories_dir, "Photo story", date(2026, 1, 1), "")

    def make_upload(color):
        buf = jpeg_bytes(color=color, size=(3000, 1000))
        return FileStorage(stream=buf, filename="upload.jpg", content_type="image/jpeg")

    name1 = storage.save_image(stories_dir, story_id, make_upload("red"))
    name2 = storage.save_image(stories_dir, story_id, make_upload("blue"))

    assert name1 == "photo-001.jpg"
    assert name2 == "photo-002.jpg"

    with Image.open(stories_dir / story_id / name1) as img:
        assert max(img.size) <= storage.MAX_IMAGE_EDGE

    thumb_path = stories_dir / story_id / storage.thumb_filename(name1)
    assert thumb_path.is_file()
    with Image.open(thumb_path) as thumb_img:
        assert max(thumb_img.size) <= storage.THUMB_MAX_EDGE


def test_save_image_keeps_png_as_png(stories_dir):
    from io import BytesIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(stories_dir, "Png story", date(2026, 1, 1), "")

    buf = BytesIO()
    Image.new("RGBA", (100, 100), color=(0, 0, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    upload = FileStorage(stream=buf, filename="upload.png", content_type="image/png")

    name = storage.save_image(stories_dir, story_id, upload)
    assert name == "photo-001.png"
    with Image.open(stories_dir / story_id / name) as img:
        assert img.format == "PNG"

    thumb_path = stories_dir / story_id / storage.thumb_filename(name)
    with Image.open(thumb_path) as thumb_img:
        assert thumb_img.format == "PNG"


def test_save_image_invalid_story_id_raises(stories_dir):
    from io import BytesIO

    from werkzeug.datastructures import FileStorage

    with pytest.raises(storage.InvalidStoryId):
        storage.save_image(stories_dir, "../nope", FileStorage(stream=BytesIO(), filename="x.jpg"))


# --- HEIC/HEIF uploads (FEATURES.md F11) --------------------------------------


def test_save_image_heic_converts_to_jpeg(stories_dir, heic_bytes):
    from PIL import Image
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(stories_dir, "Heic story", date(2026, 1, 1), "")

    buf = heic_bytes(color=(120, 40, 200), size=(3000, 1000))
    upload = FileStorage(stream=buf, filename="upload.heic", content_type="image/heic")

    name = storage.save_image(stories_dir, story_id, upload)
    assert name == "photo-001.jpg"
    with Image.open(stories_dir / story_id / name) as img:
        assert img.format == "JPEG"
        assert max(img.size) <= storage.MAX_IMAGE_EDGE


def test_save_image_heic_with_exif_orientation_corrects_rotation(stories_dir):
    from io import BytesIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(stories_dir, "Rotated heic story", date(2026, 1, 1), "")

    source = Image.new("RGB", (300, 200), color=(0, 0, 0))
    exif = source.getexif()
    exif[274] = 6  # Orientation: needs a 90-degree correction to display upright.

    buf = BytesIO()
    source.save(buf, format="HEIF", quality=80, exif=exif.tobytes())
    buf.seek(0)
    upload = FileStorage(stream=buf, filename="rotated.heic", content_type="image/heic")

    name = storage.save_image(stories_dir, story_id, upload)
    with Image.open(stories_dir / story_id / name) as img:
        assert img.format == "JPEG"
        # A 90-degree orientation correction swaps width/height: a landscape
        # 300x200 source becomes portrait 200x300 once upright.
        assert img.size == (200, 300)

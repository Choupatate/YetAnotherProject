"""Minimal, dependency-free EPUB3 export (stdlib zipfile + string templates,
no new dependency — see FEATURES.md's "no new dependencies" rule)."""

import html
import html.entities
import re
import uuid
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

MIMETYPE = "application/epub+zip"

_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_STYLE_CSS = """
body { font-family: serif; line-height: 1.5; margin: 1.5em; }
h1 { font-size: 1.6em; }
.date { font-size: 0.85em; color: #555; text-transform: uppercase; letter-spacing: 0.05em; }
img { max-width: 100%; }
figcaption { font-style: italic; font-size: 0.85em; text-align: center; color: #555; }
mark { background: #f5dfa6; }
hr.flourish { width: 4em; border: none; border-top: 2px solid #a9701c; margin: 1em auto; }
"""

_IMG_SRC_RE = re.compile(r'src="/story/([a-z0-9-]+)/media/([a-z0-9._-]+)"')
_VOID_TAG_RE = re.compile(r"<(img|hr|br)((?:\s+[^<>]*)?)>")
_HTML_ENTITY_RE = re.compile(r"&([a-zA-Z][a-zA-Z0-9]*);")
_XML_SAFE_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}

_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def _media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MEDIA_TYPES.get(ext, "application/octet-stream")


def _entities_to_unicode(fragment: str) -> str:
    """Replace named HTML entities (markdown's "smarty" extension emits
    &mdash;, &hellip;, &rsquo;, etc.) with their literal Unicode characters.
    The 5 XML-predefined entities are left alone since they're required for
    well-formed XML; every other named entity is invalid there without a
    DTD, which EPUB readers don't fetch."""

    def _sub(m):
        name = m.group(1)
        if name in _XML_SAFE_ENTITIES:
            return m.group(0)
        char = html.entities.html5.get(name + ";") or html.entities.html5.get(name)
        return char if char is not None else m.group(0)

    return _HTML_ENTITY_RE.sub(_sub, fragment)


def _self_close_void_tags(fragment: str) -> str:
    def _sub(m):
        tag, attrs = m.group(1), m.group(2).rstrip()
        if attrs.endswith("/"):
            return f"<{tag}{attrs}>"
        return f"<{tag}{attrs} />"

    return _VOID_TAG_RE.sub(_sub, fragment)


def _rewrite_images(body_html: str):
    """Rewrite /story/<id>/media/<file> srcs to epub-relative paths.

    Returns (new_html, [(story_id, filename, epub_path), ...]).
    """
    found = []

    def _sub(m):
        story_id, filename = m.group(1), m.group(2)
        epub_path = f"images/{story_id}__{filename}"
        found.append((story_id, filename, epub_path))
        return f'src="{epub_path}"'

    return _IMG_SRC_RE.sub(_sub, body_html), found


def _manifest_id(epub_path: str) -> str:
    return "res-" + re.sub(r"[^a-zA-Z0-9]", "-", epub_path)


def _story_xhtml(title: str, date_line: str, cover_img: str, body_html: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{_esc(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
<h1>{_esc(title)}</h1>
<p class="date">{_esc(date_line)}</p>
<hr class="flourish"/>
{cover_img}
{body_html}
</body>
</html>
"""


def _cover_xhtml(title: str, min_year, max_year, authors: list) -> str:
    range_line = ""
    if min_year and max_year:
        range_line = (
            f"Stories from {min_year}" if min_year == max_year
            else f"Stories from {min_year} to {max_year}"
        )
    authors_line = ", ".join(a["name"] for a in authors) if authors else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{_esc(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
<h1>{_esc(title)}</h1>
<p>{_esc(range_line)}</p>
<p>{_esc(authors_line)}</p>
</body>
</html>
"""


def _nav_xhtml(title: str, nav_items: list) -> str:
    lis = "\n".join(f'<li><a href="{href}">{_esc(t)}</a></li>' for href, t in nav_items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{_esc(title)}</title></head>
<body>
<nav epub:type="toc" id="toc">
<h1>{_esc(title)}</h1>
<ol>
{lis}
</ol>
</nav>
</body>
</html>
"""


def _manifest_item_xml(item_id: str, href: str, media_type: str) -> str:
    props = ' properties="nav"' if href == "nav.xhtml" else ""
    return f'<item id="{item_id}" href="{href}" media-type="{media_type}"{props}/>'


def _content_opf(title: str, book_id: str, manifest_items: list, spine_ids: list) -> str:
    manifest_xml = "\n".join(_manifest_item_xml(*item) for item in manifest_items)
    spine_xml = "\n".join(f'<itemref idref="{sid}"/>' for sid in spine_ids)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>
    <dc:title>{_esc(title)}</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
{manifest_xml}
  </manifest>
  <spine>
{spine_xml}
  </spine>
</package>
"""


def build_epub(title: str, min_year, max_year, authors: list, entries: list, image_loader) -> BytesIO:
    """Build a minimal EPUB3 in memory.

    `entries`: list of {"story": Story, "body_html": str} for readable
    stories, oldest first (same set/order as /book). `image_loader(story_id,
    filename)` must return raw file bytes or None if missing.
    """
    buf = BytesIO()
    zf = ZipFile(buf, "w", ZIP_DEFLATED)
    zf.writestr("mimetype", MIMETYPE, compress_type=ZIP_STORED)
    zf.writestr("META-INF/container.xml", _CONTAINER_XML)
    zf.writestr("OEBPS/style.css", _STYLE_CSS)

    manifest_items = [("style", "style.css", "text/css")]
    spine_ids = []
    nav_items = []
    embedded = set()

    def _embed_image(story_id, filename, epub_path):
        if epub_path in embedded:
            return
        data = image_loader(story_id, filename)
        if data is None:
            return
        embedded.add(epub_path)
        zf.writestr(f"OEBPS/{epub_path}", data)
        manifest_items.append((_manifest_id(epub_path), epub_path, _media_type(filename)))

    manifest_items.append(("cover", "cover.xhtml", "application/xhtml+xml"))
    spine_ids.append("cover")
    zf.writestr("OEBPS/cover.xhtml", _cover_xhtml(title, min_year, max_year, authors))

    for i, entry in enumerate(entries):
        story = entry["story"]
        rewritten, images = _rewrite_images(entry["body_html"])
        rewritten = _entities_to_unicode(rewritten)
        rewritten = _self_close_void_tags(rewritten)
        for story_id, filename, epub_path in images:
            _embed_image(story_id, filename, epub_path)

        cover_img = ""
        if story.cover:
            cover_epub_path = f"images/{story.id}__{story.cover}"
            _embed_image(story.id, story.cover, cover_epub_path)
            if cover_epub_path in embedded:
                cover_img = f'<img src="{cover_epub_path}" alt=""/>'

        item_id = f"story-{i}"
        href = f"story-{i}.xhtml"
        manifest_items.append((item_id, href, "application/xhtml+xml"))
        spine_ids.append(item_id)
        nav_items.append((href, story.title))

        date_line = story.date.strftime("%B %-d, %Y")
        if story.author:
            date_line += f" · {story.author}"

        zf.writestr(
            f"OEBPS/{href}",
            _story_xhtml(story.title, date_line, cover_img, rewritten),
        )

    manifest_items.append(("nav", "nav.xhtml", "application/xhtml+xml"))
    zf.writestr("OEBPS/nav.xhtml", _nav_xhtml(title, nav_items))

    book_id = str(uuid.uuid4())
    zf.writestr("OEBPS/content.opf", _content_opf(title, book_id, manifest_items, spine_ids))

    zf.close()
    buf.seek(0)
    return buf

"""Markdown -> HTML rendering for story bodies."""

import re
import threading
import xml.etree.ElementTree as etree

import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

EXTENSIONS = [
    "pymdownx.caret",
    "pymdownx.tilde",
    "pymdownx.mark",
    "smarty",
    "tables",
    "sane_lists",
]

_ABSOLUTE_SRC_RE = re.compile(r"^([a-z]+:)?//|^/")


class _StoryImageTreeprocessor(Treeprocessor):
    """Rewrites bare image srcs to a media URL and wraps images in <figure>,
    turning non-empty alt text into a <figcaption>. `media_base` is a path
    prefix like "/story/<id>/media" or "/people/<slug>/media" (FEATURES.md
    F14 generalized this from a hardcoded story path so person pages can
    share the same rendering)."""

    def __init__(self, md, media_base):
        super().__init__(md)
        self.media_base = media_base

    def run(self, root):
        self._process(root)
        return root

    def _process(self, parent):
        for i, child in enumerate(list(parent)):
            is_lone_image_paragraph = (
                child.tag == "p"
                and len(child) == 1
                and child[0].tag == "img"
                and not (child.text or "").strip()
                and not (child[0].tail or "").strip()
            )
            if is_lone_image_paragraph:
                img = child[0]
                self._rewrite_src(img)
                figure = self._build_figure(img)
                figure.tail = child.tail
                parent[i] = figure
            else:
                if child.tag == "img":
                    self._rewrite_src(child)
                self._process(child)

    def _rewrite_src(self, img):
        src = img.get("src", "")
        if src and not _ABSOLUTE_SRC_RE.match(src):
            img.set("src", f"{self.media_base}/{src}")

    def _build_figure(self, img):
        figure = etree.Element("figure")
        img_copy = etree.SubElement(figure, "img")
        img_copy.set("src", img.get("src", ""))
        alt = img.get("alt", "")
        img_copy.set("alt", alt)
        if alt:
            figcaption = etree.SubElement(figure, "figcaption")
            figcaption.text = alt
        return figure


class _StoryImageExtension(Extension):
    def __init__(self, media_base, **kwargs):
        self.media_base = media_base
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.treeprocessors.register(
            _StoryImageTreeprocessor(md, self.media_base), "story_images", 5
        )


_local = threading.local()


def _get_markdown() -> markdown.Markdown:
    """One `markdown.Markdown` instance per thread, reused across calls
    (`.reset()` between conversions) instead of rebuilding the extension
    chain on every story/book render. Thread-local rather than a single
    module-global so concurrent requests handled by different threads never
    share (and race on) the same parser state."""
    md = getattr(_local, "md", None)
    if md is None:
        md = markdown.Markdown(extensions=EXTENSIONS + [_StoryImageExtension(media_base="")])
        _local.md = md
    return md


def render_markdown(body: str, media_base: str) -> str:
    """Render markdown to HTML, rewriting bare image srcs to
    `<media_base>/<filename>` and wrapping them in <figure>. `media_base` is
    a path prefix with no trailing slash, e.g. "/story/<id>/media"."""
    md = _get_markdown()
    md.treeprocessors["story_images"].media_base = media_base
    md.reset()
    return md.convert(body or "")

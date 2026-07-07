"""Markdown -> HTML rendering for story bodies."""

import re
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
    """Rewrites bare image srcs to the story's media URL and wraps images in
    <figure>, turning non-empty alt text into a <figcaption>."""

    def __init__(self, md, story_id):
        super().__init__(md)
        self.story_id = story_id

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
            img.set("src", f"/story/{self.story_id}/media/{src}")

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
    def __init__(self, story_id, **kwargs):
        self.story_id = story_id
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.treeprocessors.register(
            _StoryImageTreeprocessor(md, self.story_id), "story_images", 5
        )


def render_markdown(body: str, story_id: str) -> str:
    """Render a story's markdown body to HTML, rewriting image srcs to point
    at /story/<story_id>/media/<filename> and wrapping them in <figure>."""
    md = markdown.Markdown(
        extensions=EXTENSIONS + [_StoryImageExtension(story_id=story_id)]
    )
    return md.convert(body or "")

"""Seed a few demo stories for local development / manual QA.

Usage: python scripts/seed_demo.py [stories_dir]
"""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app import storage  # noqa: E402


def _add_cover(stories_dir: Path, story_id: str, color) -> str:
    story_dir = stories_dir / story_id
    filename = "photo-001.jpg"
    Image.new("RGB", (1600, 1200), color=color).save(story_dir / filename, format="JPEG", quality=85)
    story = storage.get_story(stories_dir, story_id)
    storage.save_story(stories_dir, story_id, story.title, story.date, story.body, cover=filename)
    return filename


def seed(stories_dir: Path) -> None:
    stories_dir.mkdir(parents=True, exist_ok=True)

    bike_id = storage.create_story(
        stories_dir,
        "First bike ride",
        date(2023, 6, 18),
        "You wobbled, you laughed, and then suddenly you were just... riding.\n\n"
        "![The big moment](photo-001.jpg)\n\n"
        "We ==finally== took the training wheels off today, after weeks of *almost*.",
    )
    _add_cover(stories_dir, bike_id, (217, 164, 65))

    storage.create_story(
        stories_dir,
        "A quiet Tuesday",
        date(2024, 11, 3),
        "Nothing remarkable happened today, and that is exactly why I'm writing it down.\n\n"
        "You woke up early, padded into the kitchen in socks that didn't match, and asked "
        "for toast \"cut in triangles, not squares.\" We ate slowly. The radiator ticked. "
        "Rain came and went twice before lunch.\n\n"
        "In the afternoon you built a fort out of couch cushions and declared it a "
        "==lighthouse==, which meant I had to be a ship in trouble at least four separate "
        "times. Each time you saved me. Each time you were delighted anew, as if the ship "
        "hadn't been saved the previous three times.\n\n"
        "> \"Again,\" you said. \"But this time make it a *bigger* storm.\"\n\n"
        "We had pasta for dinner, the kind with the little shells you like because "
        "\"they hold the sauce.\" You fell asleep mid-sentence, describing a plan for "
        "tomorrow's lighthouse that involved, as far as I could tell, more pillows and "
        "possibly a flashlight.\n\n"
        "I don't have a photo of any of this. I just wanted to remember the shape of an "
        "ordinary day, since most of them go by without anyone writing them down at all.",
    )

    snow_id = storage.create_story(
        stories_dir,
        "Snow day",
        date(2025, 1, 20),
        "School was cancelled before you'd even finished breakfast, and I have never seen "
        "anyone get dressed so fast.\n\n"
        "We built a lopsided snowman with a carrot nose that kept falling out, and you "
        "insisted on giving him a name (Gerald) and a job (\"guarding the yard\").",
    )
    _add_cover(stories_dir, snow_id, (120, 150, 190))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("STORYBOOK_STORIES_DIR", "./stories")
    )
    seed(target)
    print(f"Seeded demo stories into {target.resolve()}")

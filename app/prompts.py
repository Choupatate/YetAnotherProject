"""Writing prompt source (FEATURES.md F16). A plain list of questions in a
plain text file — never generated, never inserted into a story."""

from pathlib import Path

DEFAULT_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts" / "default.txt"


def _parse_prompts_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def load_prompts(stories_dir) -> list[str]:
    """The family's override at `<stories_dir>/prompts.txt`, used instead of
    (not merged with) the default list when it exists and has at least one
    valid line. Falls back to the shipped 56-prompt default otherwise."""
    override_path = Path(stories_dir) / "prompts.txt"
    if override_path.is_file():
        override = _parse_prompts_file(override_path)
        if override:
            return override
    return _parse_prompts_file(DEFAULT_PROMPTS_PATH)

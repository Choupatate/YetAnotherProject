"""Offline voice-memo transcription (FEATURES.md F12).

Walks a stories directory, finds voice memos that don't yet have a
transcript sidecar, and writes one using faster-whisper. Meant to be run
occasionally from a laptop against the stories folder (or a copy of it —
sidecars can be copied back). Never imported by app/: its dependencies
live only in requirements-transcribe.txt, not requirements.txt.

Usage: python scripts/transcribe_memos.py ./stories --language fr --model small
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import storage  # noqa: E402


def transcribe_all(stories_dir: Path, language: str, model_size: str) -> None:
    from faster_whisper import WhisperModel

    print(f"Loading model {model_size!r} (first run downloads it, may take a while)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    for story_dir in sorted(p for p in stories_dir.iterdir() if p.is_dir()):
        pending = [m for m in storage.list_memos(story_dir) if m.transcript is None]
        for memo in pending:
            audio_path = story_dir / memo.filename
            sidecar_path = audio_path.with_suffix(".txt")
            print(f"Transcribing {story_dir.name}/{memo.filename}...")
            try:
                segments, _info = model.transcribe(str(audio_path), language=language)
                text = " ".join(segment.text.strip() for segment in segments).strip()
                sidecar_path.write_text(text + "\n", encoding="utf-8")
            except Exception as e:
                print(f"  Skipped {memo.filename}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write .txt transcript sidecars for voice memos that don't have one yet."
    )
    parser.add_argument("stories_dir", type=Path, help="Path to the stories folder (or a copy of it)")
    parser.add_argument("--language", default="fr", help="Language code for transcription (default: fr)")
    parser.add_argument("--model", default="small", help="faster-whisper model size (default: small)")
    args = parser.parse_args()

    if not args.stories_dir.is_dir():
        parser.error(f"Not a directory: {args.stories_dir}")

    transcribe_all(args.stories_dir, args.language, args.model)


if __name__ == "__main__":
    main()

---
description: Check recent commits against FEATURES.md/README.md and fill in anything undocumented
argument-hint: [number of commits to check, default 10]
---

Audit whether recent work on this branch is fully reflected in the
project's Markdown docs, and fix any gaps you find.

1. Look at the last **${ARGUMENTS:-10}** commits (`git log --oneline -n`)
   and their diffs (`git show --stat`/`git diff`) against the merge-base
   with `origin/main`. For each commit that changed application behavior
   (not a pure refactor, test-only change, or dependency bump), check:
   - Is there a corresponding `## F<N>.` section in `FEATURES.md`? Feature
     numbers are sequential (F1, F2, ...) in the order they shipped — find
     the highest existing number before assigning a new one.
   - If the change is user-visible, is it described somewhere in
     `README.md` (a new section, or an addition to an existing one)?
   - If the change added, removed, or upgraded a dependency, is it in the
     README's "Dependencies" table with an accurate one-line purpose, and
     pinned in `requirements.txt`?
   - If the change added a new top-level module or materially changed how
     an existing one fits together, is CLAUDE.md's "Architecture" section
     still accurate?
2. For anything missing, write it now, matching the existing style of the
   file you're editing (see the most recent `## F<N>.` entry in
   `FEATURES.md` for that file's tone/structure: intro paragraph, `###
   Design`, `### Tests`, a final `pytest`/`ruff` status line). Don't
   invent design rationale you don't actually know — if a commit message
   or diff doesn't make the "why" clear, look at the actual code change
   before writing the doc, rather than guessing.
3. Do **not** touch `PLAN.md` or `REVIEW.md` — both are explicitly
   historical/frozen records per CLAUDE.md, not living docs kept in sync
   with new work.
4. If nothing is missing, say so briefly and don't create empty-handed
   edits just to have made a change.

This is a documentation-only pass: don't change application code, tests,
or behavior while doing this — if you spot an actual bug or gap in the
implementation while reading through it, mention it in your summary
instead of fixing it inline.

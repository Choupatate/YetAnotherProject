---
description: Implement, test, document, and merge one feature end-to-end on its own PR
argument-hint: <feature description>
---

Ship exactly one feature end-to-end: **$ARGUMENTS**

Follow this repo's established workflow (see CLAUDE.md for the project's
philosophy and conventions — read it first if you haven't this session).
Do every step below for this one feature before starting another; if the
user asked for several features, do them one at a time, fully shipped,
rather than mixing changes from more than one into the same PR.

1. **Scope it conservatively.** Re-read CLAUDE.md's "Philosophy" section
   and `FEATURES.md`'s existing entries for related features before
   writing code. If the request conflicts with a stated philosophy point
   (no database, no build step, minimal deps, book-not-blog scope, etc.),
   stop and raise it rather than building around it silently.
2. **Branch.** Make sure you're on the session's designated feature branch
   and it's reset to the latest `origin/main` before starting new work
   (`git fetch origin main && git checkout -B <branch> origin/main` if it
   isn't already there and clean).
3. **Implement**, following the codebase's existing conventions: pure
   functions in `storage.py`/`people.py`/etc. take their directory
   explicitly, mutating API routes validate inputs via `_validate_*`
   helpers, optional update fields follow the "None means leave unchanged,
   empty clears" convention, writes go through the atomic
   write-tmp-then-`os.replace` pattern.
4. **Test.** Add pytest coverage matching the style of the nearest existing
   test file for that feature area. Run `pytest` and `ruff check .` and
   get both green before moving on.
5. **Verify in a real browser** for any UI change — start the dev server
   and drive it with Playwright (`/opt/pw-browsers/chromium`), checking a
   mobile-width viewport (390px) as well as desktop. Don't rely on pytest
   passing as proof a UI feature actually works.
6. **Document it.** Add a new `## F<N>.` section to `FEATURES.md` (next
   sequential number) describing the feature, the design decisions made,
   and any edge cases or scope cuts — follow the existing entries' style
   (intro paragraph, `### Design`, `### Tests`, final `pytest`/`ruff`
   status line). Add or extend the matching user-facing section in
   `README.md` if the feature is visible to the person using the app.
7. **Commit** with a clear, descriptive message (no mention of AI tooling
   in the message itself).
8. **Push** to the designated branch (`git push -u origin <branch>`, or
   `--force-with-lease` if the branch was just reset from `main`).
9. **Open a PR** (unless one for this branch already exists and is still
   open) — check for a PR template first and follow its structure.
10. **Watch CI.** Subscribe to the PR's activity and wait for checks to
    finish; fix and re-push if anything fails rather than merging red.
11. **Merge** once green (squash merge, matching this repo's existing merge
    history), then reset the local branch from the new `origin/main` tip
    so it's ready for the next feature.

Report back with a short summary of what shipped and the PR/merge link —
don't narrate every intermediate step as you go.

---
name: ptm-monthly-rollover
description: >-
  Use at the turn of the month, or whenever the user wants to close one out —
  "close out August", "roll over to September", "start a new month", "chốt sổ
  tháng này". Reviews what was finished and what is still open across every
  context, drives a task-by-task decision on the leftovers (carry, drop, or do
  now), then runs `ptmutils rollover` to create next month's pages and carry the
  agreed tasks forward with their ids intact, and writes a closing summary note
  on the month that ended. Always previews with `--dry-run` and gets approval
  before moving anything.
---

# Close a month and carry the rest forward

The point of this skill is not to move rows between files — `ptmutils rollover`
does that in one command. The point is the **decision** on each leftover task:
carrying everything forward unexamined is how a task list becomes a graveyard.

So: review, decide, *then* move.

## Workflow

### 1. See where things stand

```bash
ptmutils contexts
ptmutils digest --all --month <the month being closed> --json
ptmutils tasks --all --month <the month being closed> --json
```

Default the month to the one just ending. If the user says "close out August" in
September, that is `2026-08`.

### 2. Show the month that happened

Lead with what got **done**, per context. This is the part worth reading, and it
is the part the user will have forgotten:

```
August 2026

[Work]  12 done · 4 still open · 9 notes
  done  Shipped the export pipeline
  done  Reworked the settings page
  ...
[Personal]  3 done · 2 still open
  ...
```

### 3. Decide on every leftover — the actual work

Go through the open tasks and get a call on each. Do not batch-ask "carry these
forward?"; ask about the ones that need thinking about.

| Signal | What to ask |
| --- | --- |
| Carried before (`from::` present) | "This has already moved once. Is it real?" |
| Old (`added::` early in the month), no `due` | "Still want this?" |
| Overdue | "Missed its date — new date, or drop it?" |
| Added in the last few days | Carry it; no question needed |

The three outcomes:

- **Carry** — it moves to next month (the default).
- **Drop** — the user no longer wants it. Close it with `ptmutils done <id>`
  and say plainly that you are closing it, not deleting it: the line stays on
  the August page as a record.
- **Do now** — small enough to finish before rolling over. Let them.

Batch the questions into as few messages as you can. A month with fifteen
leftovers should not become fifteen round trips.

### 4. Preview

```bash
ptmutils rollover --all --dry-run
```

Show exactly what would move, per context, and confirm it matches what was
agreed. If the user dropped something, make sure it is already closed so it does
not appear here.

To close a month other than the current one:

```bash
ptmutils rollover --all --source 2026-08 --target 2026-09 --dry-run
```

### 5. Roll over

```bash
ptmutils rollover --all
```

What this does, so you can explain it:

- Creates next month's page in each vault if missing.
- Appends each open task there **keeping its id**, plus `[from:: 2026-08]`, so
  the history is visible and `ptmutils done <id>` still works.
- Rewrites the August line as `- [>] … [moved:: 2026-09]` — Obsidian's
  "forwarded" checkbox. It reads as handled, and Dataview does not count it as
  done.
- Leaves done tasks where they are.

It is safe to run twice: the second run finds nothing open to move.

### 6. Write the closing note

On the month that **ended**, in each context that had real activity:

```bash
ptmutils note --title "August wrap-up" -c nf --month 2026-08 --date 2026-08-31 \
  --body "Shipped the export pipeline and reworked the settings page. The search rewrite slipped to September, blocked on an upstream release." \
  --detail "Dropped the legacy import cleanup — not worth the effort" \
  --detail "3 tasks carried into September, all with dates this time"
```

Note the `--month` and `--date`: the wrap-up belongs on the page it is about,
not on the new one.

Keep it to what was decided and what changed. This is the entry the user will
read in a year when they wonder why something slipped.

## Hard rules

- **Always `--dry-run` first**, and always get approval before the real run.
- **Never drop a task by deleting the line.** Close it with `done` — the record
  stays.
- **Never carry silently.** Every leftover gets a decision, even if the decision
  is a one-word "yes, carry".
- **Never invent the wrap-up.** It summarises the digest and the decisions made
  in this conversation; it does not editorialise about productivity.
- **Never roll over a month the user did not name** when the intent is
  ambiguous — ask which month is being closed.

## Related

- `ptm-review` — the same read, without the month boundary
- `ptm-capture` — add whatever the review surfaces
- `ptm-plan-day` — start the new month with a real day plan

# Vault layout — the Obsidian side

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

This is what `ptmutils` writes and how to read it in Obsidian. The full contract
lives in [`src/ptm/specs.md`](../src/ptm/specs.md); this page is the practical
version.

## One vault per context

A **context** is a stream of work. Each one is its own Obsidian vault:

```
~/Documents/vaults/
├── work/                      # context: work
│   ├── _ptm_dashboard.md
│   └── notes/
│       ├── 2026-08.md
│       └── 2026-07.md
└── personal/                  # context: priv
    ├── _ptm_dashboard.md
    └── notes/
        └── 2026-08.md
```

They are separate vaults, not folders, because you open them as separate
Obsidian workspaces and probably sync them to different places. `ptmutils`
bridges them: `--all` reads across every registered context in one command.

`ptmutils` owns exactly two things in a vault — `notes/*.md` files named
`YYYY-MM.md`, and `_ptm_dashboard.md`. **Everything else is yours** and is never
read or written. Put your meeting notes, references and daily notes wherever you
like.

## The month page

```markdown
---
context: Work
context_slug: work
month: 2026-08
type: ptm-month
tags: [ptm]
---

# Work — August 2026

## Tasks

- [ ] Fix login redirect [id:: t-da621] [added:: 2026-08-24] [due:: 2026-08-30] [prio:: high]
- [x] Write the monthly report #admin [id:: t-ad91a] [added:: 2026-08-24] [done:: 2026-08-24]
- [>] Rewrite the search index [id:: t-3c8f0] [added:: 2026-08-02] [moved:: 2026-09]

## Log

### 2026-08-24 (Mon)

#### 09:42 — Sprint planning
tags:: #meeting

Decided to defer the rewrite to September.

**Details**
- Rewrite deferred; revisit once the upstream lands

#### 14:10 — Afternoon sync

Reviewed the backlog with the team.
```

### Tasks

Every checklist item on the page sits under `## Tasks`, so the month's open work
is visible in one place rather than scattered through the log.

`[key:: value]` are **Dataview inline fields**. On a checklist line Dataview
indexes them **per task**, so a `TASK` query resolves to the individual item —
which is why tasks live on checkbox lines and notes do not.

| Field | Written by | Meaning |
| --- | --- | --- |
| `id` | `task` | The handle `done`/`undone` take. Survives a rollover. |
| `added` | `task` | Date the task was created |
| `due` | `--due` | Target date |
| `prio` | `--prio` | `low` / `med` / `high` |
| `done` | `done` | Completion date |
| `moved` | `rollover` | The month it was carried into |
| `from` | `rollover` | The month it was carried from |

Checkbox states:

| Box | Meaning |
| --- | --- |
| `- [ ]` | Open |
| `- [x]` | Done |
| `- [>]` | Carried into a later month by `rollover` |

`[>]` is Obsidian's "forwarded" checkbox. Dataview does not count it as
completed, so a forwarded task never inflates a "done this month" query — but it
still reads as *handled* rather than *ignored* on the page it left.

### Log

Notes are appended under `## Log`, grouped by day:

- `### YYYY-MM-DD (Ddd)` — one per day, created on first use
- `#### HH:MM — Title` — one per note
- optional `tags:: #a #b` line directly beneath the heading
- a Markdown body paragraph, then an optional `**Details**` bullet list

The **body** is what a standup or a summary quotes. The **Details** bullets are
for you, months later: decisions, gotchas, follow-ups.

### Adding your own sections

A section runs until the next `## ` heading, so you can add your own `## Links`
or `## Retro` section anywhere on the page and `ptmutils` will leave it alone.

## Editing by hand

Hand-editing is expected, not tolerated:

- Tick a box in Obsidian → `ptmutils tasks` sees it as done. (It won't have a
  `done::` date; only the CLI stamps that.)
- Type `- [ ] Something` under `## Tasks` → it lists and counts. It has no id,
  so `ptmutils done` can't address it until you add `[id:: t-xxxxx]` yourself.
- Reword a task, add fields, reorder lines → all fine.
- Anything the parser doesn't recognise is ignored, never rewritten.

The CLI only ever modifies an existing line for `done`, `undone` and `rollover`.
Everything else appends.

## The dashboard

`ptmutils init` writes `_ptm_dashboard.md` at the vault root — open it first in
Obsidian. It needs the **Dataview** plugin.

| Section | Shows |
| --- | --- |
| Open tasks | Everything not done and not forwarded, soonest due first |
| Open tasks with a due date | The subset that has a deadline |
| Everything done | Completed tasks, most recent first |
| Month pages | Every page in the vault, newest month first |

The dashboard is yours once written — `init` will not overwrite your edits;
`init --force` restores the shipped version.

Useful queries to add yourself:

````markdown
```dataview
TASK FROM "notes"
WHERE !completed AND due AND due < date(today)
SORT due ASC
```

```dataview
TASK FROM "notes"
WHERE !completed AND prio = "high"
```
````

## Syncing

Out of scope for the tool, and deliberately so. Git, iCloud, Obsidian Sync — all
work, because everything here is plain Markdown. Because contexts are separate
vaults, you can sync a work vault and a personal vault to entirely different
places.

## Related

- [`docs/ptmutils.md`](./ptmutils.md) — command reference
- [`src/ptm/specs.md`](../src/ptm/specs.md) — the format contract

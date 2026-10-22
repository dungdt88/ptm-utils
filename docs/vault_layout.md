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
│   ├── notes/
│   │   ├── 2026-08.md
│   │   └── 2026-07.md
│   └── goals/
│       ├── 2026.base          # the year's goal table
│       ├── 2026/              # one note per goal
│       └── _templates/goal.md
└── personal/                  # context: priv
    ├── _ptm_dashboard.md
    └── notes/
        └── 2026-08.md
```

They are separate vaults, not folders, because you open them as separate
Obsidian workspaces and probably sync them to different places. `ptmutils`
bridges them: `--all` reads across every registered context in one command.

`ptmutils` owns three things in a vault — `notes/*.md` files named
`YYYY-MM.md`, `_ptm_dashboard.md`, and the `goals/` folder (see
[Yearly goals](#yearly-goals)). **Everything else is yours** and is never read
or written. Put your meeting notes, references and daily notes wherever you
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

On a month page the CLI only ever modifies an existing line for `done`,
`undone` and `rollover`. Everything else appends.

## The dashboard

`ptmutils init` writes `_ptm_dashboard.md` at the vault root — open it first in
Obsidian. It needs the **Dataview** plugin.

| Section | Shows |
| --- | --- |
| Open tasks | Everything not done and not forwarded, soonest due first |
| Open tasks with a due date | The subset that has a deadline |
| Everything done | Completed tasks, most recent first |
| Month pages | Every page in the vault, newest month first |
| Goals this year | This year's goals with status, area and milestones done (`2/5`) |

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

## Yearly goals

A year's plan — usually under ten resolutions — is the Obsidian take on a Notion
database: **one note per goal** in a folder per year, and a **Bases** table over
the folder. Bases is a core Obsidian plugin (Settings → Core plugins → Bases), so
the table needs nothing installed.

| Notion | Obsidian |
| --- | --- |
| The year's database | `goals/2026/` plus the `goals/2026.base` table |
| A row's page | `goals/2026/Plan for living abroad.md` |
| Status | `status:` property — `not-started`, `in-progress`, `done` |
| Tags | `area:` property — one label, e.g. `family`, `mika` |
| The page description | `## Description` |
| The checklist in the page | `## Milestones` |
| Comments | `## Progress` — one dated line per update |
| Comment count | the table's **Last edited** column (`file.mtime`) |

Each vault keeps its own goals: work goals in the work vault, personal ones in
the personal vault.

### A goal note

```markdown
---
type: ptm-goal
id: g-4be07
status: in-progress
area: mika
created: 2025-12-30
tags: [ptm]
---

# Improve operation and productivity

## Description

- Apply CMS webapp to improve productivity
- Make operation more standard so it can be delegated

## Milestones

- [ ] Salary & payroll management
- [x] Map customer payments to SAPO order ids

## Progress

- 2025-12-30 — Plan written
- 2026-03-14 — Payment ↔ SAPO mapping live
```

### Working in Obsidian only

Everything works without the CLI:

1. **Start the year** — run `ptmutils goal init --year 2027` once per vault, or
   create `goals/2027/` and copy last year's `.base`, changing the folder in its
   `file.inFolder(...)` filter.
2. **Point the Templates core plugin** at `goals/_templates` (Settings →
   Templates → Template folder location). Create a note in `goals/2027/`, run
   *Templates: Insert template* → `goal`, and the skeleton fills in with the
   title and today's date.
3. **Open `goals/2027.base`.** The *Goals* view lists every goal; *By status*
   groups them. Click a status cell to change it; click a title to open the note.
4. **Record progress** by adding a line at the end of `## Progress`:
   `- 2027-03-14 — what happened`. Tick milestones as you go.

To make the table the first thing you see, embed it in any note with
`![[goals/2027.base]]`.

### From the terminal

```bash
ptmutils goal add "Plan for living abroad" -c priv --area family --year next
ptmutils goal log abroad "Shortlisted three cities"
ptmutils goal check abroad "visa"
ptmutils goals --all
```

See [`ptmutils.md`](./ptmutils.md#goal--yearly-goals) for every option.

### Rules worth knowing

- **The folder is the year.** Every `.md` directly in `goals/2026/` is a 2026
  goal, with or without frontmatter — the same set the table shows.
- **The file name is the title.** Rename the note in Obsidian to rename the goal.
- **Progress lines stay in shape** `- YYYY-MM-DD — text` so the CLI can read
  them back; anything else in the section is kept but not parsed.
- **A new year starts fresh.** Nothing is carried over automatically; add the
  goals you want to keep into the new year's folder.
- The CLI edits a goal's `status:` line and milestone checkboxes, and appends to
  `## Milestones` and `## Progress`. It never rewrites the rest, and never
  overwrites a `.base` or the template you have customised.

## Syncing

Out of scope for the tool, and deliberately so. Git, iCloud, Obsidian Sync — all
work, because everything here is plain Markdown. Because contexts are separate
vaults, you can sync a work vault and a personal vault to entirely different
places.

## Related

- [`docs/ptmutils.md`](./ptmutils.md) — command reference
- [`src/ptm/specs.md`](../src/ptm/specs.md) — the format contract

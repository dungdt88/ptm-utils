# ptm — Module Specification

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

This is the source of truth for `ptmutils`' behaviour. Update it **before**
changing the code — if code and spec disagree, that is a bug.

## Purpose

`ptmutils` is a personal task manager that stores everything as plain Markdown
inside Obsidian vaults. It exists so that capturing a note or a task costs one
command from whatever terminal you are already in, while the result stays a
normal Obsidian note you can read, edit and link by hand.

It is deliberately **offline and credential-free**. It talks to no external
service. Issue trackers are out of scope — a Jira key is just text in a task.

## Personas

| Persona | What they need |
| --- | --- |
| The user, at a terminal | Capture a task or a note in one line, without opening Obsidian |
| The user, in Obsidian | Read the month back, tick things off by hand, link freely |
| An AI agent | Read structured JSON out, write well-formed entries in |

## Core model

Three nouns, and nothing else:

1. **Context** — a stream of work (`Work`, `Personal`). **One Obsidian
   vault per context.** The vault is the context; the tool keeps a registry
   mapping a short slug to a vault path.
2. **Month page** — one Markdown file per month inside a context's vault, at
   `<vault>/<notes_dir>/YYYY-MM.md`. This is the unit the user thinks in:
   *"my August page for Work"*.
3. **Entry** — either a **task** (a checklist item) or a **note** (a timestamped
   log entry). Both live on the month page, in their own section.

There is no database and no index. The Markdown files *are* the state, so
anything Obsidian or a text editor does to them is legitimate input.

Beside the monthly rhythm sits a yearly one:

4. **Goal** — a yearly resolution ("Plan for living abroad"). One note per
   goal, at `<vault>/<goals_dir>/YYYY/<Title>.md`, carrying a status, an area,
   a description, a milestone checklist and a dated progress log. A year's goals
   are a small set (usually under ten) that live all year, so each one gets its
   own note rather than a line on a month page. See [Goals](#goals).

### Why one vault per context

Contexts are separated at the vault boundary rather than by folder because the
user opens them as separate Obsidian workspaces, syncs them differently
(a work vault and a personal vault do not belong in the same sync target), and
may not want them cross-linked. The cost is that cross-context reads fan out
over several vaults — `--all` does this, and it is cheap because a month page is
a small file.

## Vault layout

```
~/Documents/vaults/work/          # one context = one vault
├── _ptm_dashboard.md                  # written by `ptmutils init`
├── notes/                             # $PTM_NOTES_DIR, default "notes"
│   ├── 2026-08.md                     # this month
│   └── 2026-07.md
└── goals/                             # $PTM_GOALS_DIR, default "goals"
    ├── 2026.base                      # the year's table view (Obsidian Bases)
    ├── 2026/
    │   ├── Plan for living abroad.md  # one note per goal
    │   └── Start creating robots.md
    └── _templates/
        └── goal.md                    # for creating a goal by hand in Obsidian
```

- `ptmutils` owns `notes/*.md` matching `YYYY-MM.md`, `_ptm_dashboard.md`, and
  the goals folder: `goals/YYYY/*.md`, `goals/YYYY.base` and
  `goals/_templates/goal.md`.
  **Everything else in the vault is the user's** and is never read or written.
- The notes folder stays **flat** — no year nesting. A decade of monthly pages is
  120 files, which every tool handles fine.
- A file in `notes/` whose stem is not a valid `YYYY-MM` is ignored entirely.

### Sharing a vault with another tool

A vault may already be in use by something else — a work-log tool may already
keep `worklog/`, `standups/` and its own `_dashboard.md` in one. `ptmutils`
therefore claims **`_ptm_dashboard.md`**, not `_dashboard.md`, and confines
everything else to `notes/` and `goals/` (both renameable per context). The two tools' file sets are disjoint by
construction, so one vault can hold both without either needing to know about
the other.

This follows the usual convention for a shared vault: one
top-level folder per kind, kinds never nest, and a tool only writes inside its
own.

## Page format — the contract

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
```

### Rules

| Element | Rule |
| --- | --- |
| Frontmatter | `type: ptm-month` identifies the page. `context_slug` is the registry key. |
| `## Tasks` | Every checklist item on the page lives here. New tasks append to the end of the section. |
| `## Log` | Notes only. Day headings `### YYYY-MM-DD (Ddd)`, entries `#### HH:MM — Title`. |
| Section end | A section runs until the next `## ` heading, so a user may add their own `## ` sections and the tool will leave them alone. |
| Task fields | Dataview **per-item** inline fields, `[key:: value]`, so Dataview's `TASK` queries resolve per task rather than per page. |
| Note fields | A `tags:: #a #b` line directly under the entry heading. |

### Checkbox states

| Box | Status | Meaning |
| --- | --- | --- |
| `- [ ]` | `open` | Not done |
| `- [x]` | `done` | Done; carries `[done:: YYYY-MM-DD]` |
| `- [>]` | `moved` | Carried into a later month by `rollover`; carries `[moved:: YYYY-MM]` |

`[>]` is Obsidian's "forwarded" checkbox. Dataview does not count it as
completed, so a forwarded task never inflates a "done this month" query, and it
still reads as *handled* rather than *ignored* on the page it left.

### Task ids

`t-` plus five hex characters, derived from the context, month, text and
creation time, retried on collision against every id already in that context's
vault. Ids are the handle `done`/`undone` take, so they must be short enough to
retype and stable enough to survive the task being carried into another month —
**`rollover` preserves the id.**

A task typed by hand in Obsidian has no id. It still parses, lists, and counts;
it simply cannot be addressed by `done <id>` until an id is added.

## Goals

A year's plan is a folder of goal notes plus an Obsidian **Bases** view over
them — the same shape as a Notion database (one row per goal, each row a page).
Bases is a core Obsidian plugin, so the table needs nothing installed; the
dashboard's goal section uses Dataview like the rest of it.

Each context keeps its own goals in its own vault: work goals in the work vault,
personal ones in the personal vault. There is no cross-year carry-over — each
year's plan is written fresh, and bringing a goal forward is a human decision
(`goal add` it again in the new year).

### Goal note — the contract

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

| Element | Rule |
| --- | --- |
| Location | `<goals_dir>/YYYY/<Title>.md`. **The folder is the year**, and every `.md` directly inside it is a goal, with or without frontmatter — the same set the Bases view shows. |
| Title | The file name. Characters Obsidian forbids or that break `[[links]]` (`\ / : * ? " < > \| # ^ [ ]`) are dropped when the CLI names a file. |
| `type` | `ptm-goal`. Written by the CLI and the template; not required to read a note. |
| `id` | `g-` plus five hex characters, unique within the context. Hand-made goals have none and are addressed by title. |
| `status` | `not-started`, `in-progress` or `done`. Missing reads as `not-started`; any other hand-typed value is read back verbatim. |
| `area` | One free-text label (`mika`, `family`). Optional. The Notion "tag". |
| `created` | `YYYY-MM-DD`. |
| `## Description` | Free Markdown. |
| `## Milestones` | Checklist items. `[x]`/`[X]` is done, anything else open. |
| `## Progress` | One line per entry, `- YYYY-MM-DD — text`, appended in the order written. Lines in another shape are kept but not parsed. |

Sections end at the next `## ` heading, so a user may add their own sections.
"Last edited" is the file's modification time, which Bases shows natively —
there is no `updated:` property to drift out of date.

### The year view — `YYYY.base`

```yaml
filters:
  and:
    - file.inFolder("goals/2026")
properties:
  note.status:
    displayName: Status
  note.area:
    displayName: Area
  file.mtime:
    displayName: Last edited
views:
  - type: table
    name: Goals
    order:
      - file.name
      - note.status
      - note.area
      - file.mtime
  - type: table
    name: By status
    groupBy:
      property: note.status
      direction: ASC
    order:
      - file.name
      - note.area
      - file.mtime
```

Written when a year's first goal is added or by `goal init`. Never overwritten
without `--force`, so the user may add views and columns. Bases cannot count
checkboxes, so the milestone count (`2/5`) appears in the CLI and the dashboard,
not here.

### The template — `_templates/goal.md`

The goal-note skeleton using the core **Templates** plugin's `{{title}}` and
`{{date:YYYY-MM-DD}}` variables, so a goal created by hand in Obsidian matches
what the CLI writes. Written by `goal init`; never overwritten without
`--force`. It sits outside every year folder, so it is never read as a goal.

### Addressing a goal

Commands that take a `GOAL` resolve it, within the selected context or every
context when none is given, as:

1. an **id** (`g-4be07`), in any year;
2. otherwise a **title** in `--year` (default this year): an exact
   case-insensitive match, else a unique case-insensitive substring.

No match, or several, is a `PtmError` that lists the candidates.

## Configuration

Resolution order for `ptm.env`: the current directory and its parents, then the
directory holding the module and its parents, then `$XDG_CONFIG_HOME/ptm/`. All
keys are optional.

| Key | Default | Meaning |
| --- | --- | --- |
| `PTM_CONTEXTS_FILE` | `$XDG_CONFIG_HOME/ptm/contexts.yaml` | The context registry |
| `PTM_DEFAULT_CONTEXT` | — | Context used when `--context` is omitted |
| `PTM_NOTES_DIR` | `notes` | Month-page folder inside each vault |
| `PTM_GOALS_DIR` | `goals` | Goals folder inside each vault |

The registry, managed by `ptmutils context add|remove|default`:

```yaml
default: nf
contexts:
  nf:
    name: Work
    vault: ~/Documents/vaults/work
  priv:
    name: Private
    vault: ~/Documents/vaults/private
```

When exactly one context is registered it is the default, whether or not
`default:` says so. A context may override the folders with `notes_dir:` and
`goals_dir:`; the registry records them only when they differ from the default.

## Commands

| Command | Behaviour |
| --- | --- |
| `init` | Create `notes/`, this month's page, and `_ptm_dashboard.md`. Never overwrites an existing dashboard without `--force`. |
| `context add\|remove\|default` | Manage the registry. `remove` forgets the context; it never touches the vault. |
| `contexts` | List contexts with month and open-task counts. |
| `vault` | Resolved paths and statistics for a context. |
| `page` | Print a month page or, with `--path`, just its path. `--create` writes it if missing. |
| `note` | Append a timestamped entry under today's day heading, creating the page and heading as needed. |
| `task` | Append a checklist item to `## Tasks`, print the new id. |
| `tasks` | List checklist items. Defaults to `--status open` and hides `moved`. |
| `done` / `undone` | Flip a checkbox by id, stamping or clearing `done::`. |
| `search` | Substring match over tasks and notes in a context, or `--all` of them. |
| `digest` | Per-context summary of a period: done, still open, notes. |
| `rollover` | Carry a month's open tasks into the next month's page. |
| `goal init` | Create a year's goals folder, its `.base` view and the goal template. |
| `goal add` | Create a goal note (and the year's folder and `.base` if missing), print the new id. |
| `goal show` | Print a goal note; `--json` gives its fields, milestones and progress. |
| `goal log` | Append a dated line to `## Progress`. A `not-started` goal becomes `in-progress`. |
| `goal status` | Set `status:` to `not-started`, `in-progress` or `done`. |
| `goal milestone` | Append an open item to `## Milestones`. |
| `goal check` / `goal uncheck` | Tick or untick one milestone, matched by a unique substring of its text. |
| `goals` | List a year's goals with status, area, milestone count and last progress date. |

Every read command takes `--json`. Every write command takes `--dry-run`.

`--context/-c` selects one context; `--all/-a` selects every registered one and
is available on `init`, `vault`, `tasks`, `search`, `digest`, `rollover` and
`goals`.

`--year` on the goal commands takes `YYYY`, `this`, `last`, `next` or `+/-N`,
and defaults to this year. `goal add --year next` is how a plan written in late
December lands in the coming year.

### Rollover contract

For each selected context, taking `--source` (default: this month) and
`--target` (default: the month after source):

1. Read every task in source whose status is `open`.
2. Create the target page if missing.
3. Append each task to the target's `## Tasks`, **preserving the id** and adding
   `[from:: <source month>]`. `due` and `prio` carry over; a stale `moved::` is
   dropped.
4. Rewrite the source line as `- [>] … [moved:: <target month>]`.

Tasks that are `done` or already `moved` stay put. `--dry-run` reports what
would move and writes nothing. Running it twice is safe: the second run finds no
open tasks in the source.

## Safety model

- **The vault is the user's.** Only `notes/YYYY-MM.md`, `_ptm_dashboard.md` and
  the goals files listed under [Vault layout](#vault-layout) are ever written.
  `context remove` deletes nothing on disk.
- **Writes are locked.** Every page edit takes an exclusive `flock` on the file,
  so two concurrent agent sessions produce two entries, never a lost one.
  A new goal note is created exclusively: an existing file of that name is an
  error, never overwritten.
- **Reads tolerate hand editing.** Anything the user types into a page in
  Obsidian parses back or is ignored — never rejected, never rewritten.
- **Only these modify an existing line:** `done`, `undone` and `rollover` (a
  task's checkbox); `goal status` and `goal log` (the goal's `status:` line);
  `goal check` and `goal uncheck` (a milestone's checkbox). Every other write
  appends. Frontmatter is edited line by line, never re-serialised, so
  properties the user added in Obsidian survive untouched.
- **No network, no credentials, no telemetry.**

## Error handling

User-facing failures raise `PtmError` and print `error: <message>` to stderr with
exit code 1 — no traceback. Anything else is a bug and is allowed to trace.

## Out of scope

- Syncing vaults (git, iCloud, Obsidian Sync) — the user's choice.
- Jira, Confluence, or any other issue tracker. Separate tooling covers those;
  this tool deliberately does not duplicate them.
- Recurring tasks, dependencies, time tracking, priorities beyond a flat label.
- Editing or deleting note entries or goal progress lines. Fix those by hand in
  Obsidian.
- Carrying goals from one year into the next. Each year's plan is written
  fresh; the user decides what to bring forward.
- Goals in `search` and `digest`. Goals are read through `goals` and `goal show`.

## Changelog

| Date | Author | Description |
|------|--------|-------------|
| 2026-08-24 | AI-assisted | Initial spec: contexts as vaults, monthly pages, tasks + log sections, rollover |
| 2026-08-24 | AI-assisted | Dashboard renamed `_dashboard.md` → `_ptm_dashboard.md` so a vault can be shared with another vault tool |
| 2026-10-20 | AI-assisted | Yearly goals: `goals/YYYY/` notes, a Bases view per year, a template, the `goal …` and `goals` commands, `PTM_GOALS_DIR`, and a goals section on the dashboard |

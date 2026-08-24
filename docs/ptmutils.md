# ptmutils — Personal Task Management CLI

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

## Overview

`ptmutils` keeps your tasks and notes in **Obsidian vaults**, as plain Markdown.

- **One vault per context.** A context is a stream of work — `Work`,
  `Personal`. Each gets its own Obsidian vault, so they sync separately and never
  cross-link by accident.
- **One page per month.** Inside a vault, `notes/2026-08.md` is *"my August
  page"*. Tasks live in a `## Tasks` section at the top; notes are appended to a
  dated `## Log` below.
- **The files are the state.** No database, no index. Edit anything by hand in
  Obsidian and the CLI reads it back.

Fully offline: no credentials, no network calls. Issue trackers are out of scope
— a separate tool handles those, and this one does not duplicate it.

## Prerequisites

- Python 3.11+
- Obsidian (optional — the tool works fine without it; Obsidian is just the nice
  way to read the result)

## Installation

```bash
./install.sh
```

Installs `ptmutils`, links the agent skills into `~/.claude/skills/`, and writes
a starter `ptm.env`. Re-run it after `git pull` to upgrade. `./install.sh --check`
verifies without changing anything.

## Setup

```bash
ptmutils context add work --vault ~/Documents/vaults/work     --name "Work"
ptmutils context add priv --vault ~/Documents/vaults/personal --name "Personal"
ptmutils init --all
```

`init` creates `notes/`, this month's page and an Obsidian dashboard in each
vault. Then open each vault in Obsidian and install the **Dataview** plugin.

## Configuration

Optional. `ptmutils` reads `ptm.env`, discovered from the current directory
upwards, then next to the module, then `~/.config/ptm/ptm.env`:

```ini
# Where the context registry lives
PTM_CONTEXTS_FILE=~/.config/ptm/contexts.yaml

# Context used when a command runs without --context
PTM_DEFAULT_CONTEXT=nf

# Month-page folder inside each vault
PTM_NOTES_DIR=notes
```

The registry itself is YAML, managed by `ptmutils context`:

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

With exactly one context registered, it is the default automatically.

## Vault layout

```
~/Documents/vaults/work/          # one context = one vault
├── _ptm_dashboard.md                  # written by `ptmutils init`
└── notes/
    ├── 2026-08.md                     # this month
    └── 2026-07.md
```

`ptmutils` owns `notes/*.md` and `_ptm_dashboard.md`. Everything else in the vault is
yours and is never touched. See [vault_layout.md](./vault_layout.md) for the page
format and the Dataview queries.

## Commands

Every read command takes `--json`. Every write command takes `--dry-run`.
`--context/-c` picks one context; `--all/-a` fans out across all of them.

### `task` — add a checklist item

```bash
ptmutils task "Fix login redirect" --due 2026-08-30 --prio high
ptmutils task "Renew passport" -c priv --due +30
ptmutils task "Write the report" --tag admin --month next
```

Prints the new task id, which is how you check it off later.

| Option | Description |
| --- | --- |
| `--context`, `-c` | Context slug (default: the default context) |
| `--due` | `YYYY-MM-DD`, `today`, `tomorrow`, or `+N` days |
| `--prio` | `low`, `med`, `high` |
| `--tag` | Obsidian tag without the `#`; repeatable |
| `--month` | Target month: `YYYY-MM`, `this`, `next`, `last`, `+/-N` (default this) |
| `--dry-run` | Print the Markdown line; write nothing |
| `--json` | Emit the task as JSON |

### `tasks` — list checklist items

```bash
ptmutils tasks                      # open tasks in the default context
ptmutils tasks --all                # across every context
ptmutils tasks --due-before today   # overdue
ptmutils tasks --status done --month last
ptmutils tasks --all --json         # feed a skill
```

| Option | Description |
| --- | --- |
| `--status` | `open` (default), `done`, `moved` |
| `--any-status` | Open and done together |
| `--include-moved` | Also show tasks carried into a later month |
| `--month` | Only this month page |
| `--due-before` | Only tasks due on or before a date |
| `--prio`, `--tag`, `--grep` | Filters |

### `done` / `undone` — tick a task off

```bash
ptmutils done t-da621
ptmutils done t-da621 t-ad91a --date yesterday
ptmutils undone t-da621
```

Ids are searched across every context, so you rarely need `--context`. `done`
stamps `[done:: YYYY-MM-DD]`; `undone` clears it.

### `note` — append a timestamped note

```bash
ptmutils note --title "Sprint planning" \
  --body "Decided to defer the rewrite to September." \
  --detail "Revisit once the SDK lands" --tag meeting

git log --oneline -10 | ptmutils note --title "Session wrap-up" --body -
```

| Option | Description |
| --- | --- |
| `--title` | **Required.** The entry heading |
| `--body` | Body Markdown; `-` reads stdin |
| `--body-file` | Read the body from a file (`-` = stdin) |
| `--detail` | A detail bullet; repeatable |
| `--tag` | Obsidian tag without the `#`; repeatable |
| `--date` | `YYYY-MM-DD`, `today`, `yesterday`, `-N` (default today) |
| `--time` | `HH:MM` (default now) |

Notes land under a `### YYYY-MM-DD (Ddd)` heading, created once per day.

### `search` — find anything

```bash
ptmutils search "redirect"
ptmutils search "passport" --all
ptmutils search "migration" --months 3 --json
```

Matches task text, task fields, note titles, bodies, details and tags.

### `digest` — summarise a period

```bash
ptmutils digest                       # this month so far, default context
ptmutils digest --all                 # every context
ptmutils digest --last-month
ptmutils digest --week                # this Monday → today
ptmutils digest --since 2026-07-01 --until 2026-07-15 --json
```

Per context: what was completed, what is still open, and the notes in range.

### `rollover` — carry open tasks into next month

```bash
ptmutils rollover --all --dry-run     # see what would move
ptmutils rollover --all
ptmutils rollover -c nf --source 2026-07 --target 2026-09
```

Open tasks are appended to the target page **keeping their id**, tagged
`[from:: 2026-08]`. The source line becomes `- [>] … [moved:: 2026-09]` —
Obsidian's "forwarded" checkbox, so it reads as handled without counting as
done. Done tasks stay put. Running it twice is safe.

### `page` — read or locate a month page

```bash
ptmutils page                         # print this month's page
ptmutils page --month last
ptmutils page --path                  # just the path, for piping into an editor
ptmutils page --month next --create
```

### `contexts`, `context`, `vault`, `init`

```bash
ptmutils contexts                     # slug, name, month count, open tasks
ptmutils context add <slug> --vault DIR --name NAME [--default]
ptmutils context remove <slug>        # forgets it; the vault is untouched
ptmutils context default <slug>
ptmutils vault --all                  # resolved paths and statistics
ptmutils init --all [--month M] [--force]
```

## Typical use

**In the moment** — you are in a terminal and something comes up:

```bash
ptmutils task "Fix the password-reset redirect" --due +5 --prio high
```

**End of a session** — record what happened, so you can find it in six months:

```bash
ptmutils note --title "Shipped the export pipeline" \
  --detail "Scope guard is CI-gated — loosening it needs the profile updated too"
```

**Morning** — what am I doing today:

```bash
ptmutils tasks --all --due-before +7
```

**End of month** — close it out and carry the rest forward:

```bash
ptmutils digest --all
ptmutils rollover --all --dry-run
ptmutils rollover --all
```

Or let the agent skills do it: `/ptm-capture`, `/ptm-review`, `/ptm-plan-day`,
`/ptm-monthly-rollover`.

## Notes and limits

- **Hand-editing is expected.** Tick a box in Obsidian and `ptmutils tasks` sees
  it. A task typed by hand has no id, so it lists but cannot be addressed by
  `done <id>` until you add one.
- **Concurrency-safe.** Every page write takes an exclusive `flock`, so two
  agent sessions writing at once produce two entries, never a lost one.
- **Append-first.** Only `done`, `undone` and `rollover` modify an existing line.
  Note entries are never edited or deleted by the tool.
- **Local only.** Syncing vaults (git, iCloud, Obsidian Sync) is your choice.

## Related

- [`src/ptm/specs.md`](../src/ptm/specs.md) — the behaviour and page-format contract
- [`docs/vault_layout.md`](./vault_layout.md) — the Obsidian side
- [`skills/`](../skills) — the agent skills that drive this CLI

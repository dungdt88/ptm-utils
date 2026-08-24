# ptm-utils — Personal Task Management

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

Tasks and notes in **Obsidian**, driven from the terminal — or from an AI agent
in whatever repo you happen to be in.

- **One vault per context.** `Work`, `Personal` — separate Obsidian
  vaults, so they sync separately and never cross-link by accident.
- **One page per month.** `notes/2026-08.md` is *"my August page"*. Checklist
  tasks in a `## Tasks` section, timestamped notes in a `## Log` below.
- **Plain Markdown, no database.** Edit anything by hand in Obsidian; the CLI
  reads it straight back.
- **Offline.** No credentials, no network, no telemetry.

Issue trackers are out of scope on purpose — a separate tool covers those,
and this one does not duplicate it.

## Install

```bash
git clone <this repo> && cd ptm-utils
./install.sh
```

Installs the `ptmutils` CLI, links the agent skills into `~/.claude/skills/`,
and writes a starter config. Re-run it after `git pull` to upgrade;
`./install.sh --check` verifies without changing anything.

Requires Python 3.11+. Obsidian is optional — it is just the pleasant way to
read what the tool writes.

## Set up

```bash
ptmutils context add work --vault ~/Documents/vaults/work     --name "Work"
ptmutils context add priv --vault ~/Documents/vaults/personal --name "Personal"
ptmutils init --all
```

Then open each vault in Obsidian and install the **Dataview** plugin.

## Use it

```bash
# Capture
ptmutils task "Fix the password-reset redirect" --due 2026-08-30 --prio high
ptmutils task "Renew passport" -c priv --due +30
ptmutils note --title "Sprint planning" --body "Deferred the rewrite to September." \
              --detail "Blocked on an upstream release"

# Read back
ptmutils tasks --all                    # everything open, every context
ptmutils tasks --due-before today       # overdue
ptmutils search "redirect" --all
ptmutils digest --all                   # this month: done, open, notes

# Close things
ptmutils done t-da621

# End of month
ptmutils rollover --all --dry-run
ptmutils rollover --all
```

Every read command takes `--json`. Every write command takes `--dry-run`.

## What a month page looks like

```markdown
---
context: Work
month: 2026-08
type: ptm-month
---

# Work — August 2026

## Tasks

- [ ] Fix login redirect [id:: t-da621] [added:: 2026-08-24] [due:: 2026-08-30] [prio:: high]
- [x] Write the monthly report [id:: t-ad91a] [done:: 2026-08-24]
- [>] Rewrite the search index [id:: t-3c8f0] [moved:: 2026-09]

## Log

### 2026-08-24 (Mon)

#### 09:42 — Sprint planning
tags:: #meeting

Decided to defer the rewrite to September.

**Details**
- Revisit once the upstream lands
```

`[key:: value]` are Dataview inline fields, indexed **per checklist item**, so
`TASK` queries in Obsidian resolve to individual tasks. `[>]` is the "forwarded"
checkbox — a task carried into a later month reads as handled without counting
as done.

`ptmutils` owns only `notes/YYYY-MM.md` and `_ptm_dashboard.md`. The rest of the
vault is yours.

## Agent skills

Installed into `~/.claude/skills/`, so they work from any repo:

| Skill | Use it when |
| --- | --- |
| `ptm-capture` | "add a task", "note this down", "remind me to…" |
| `ptm-review` | "what's open?", "what's overdue?", "review my month" |
| `ptm-plan-day` | "plan my day", "what should I work on" |
| `ptm-monthly-rollover` | "close out August", "roll over to September" |

## Command reference

| Command | Does |
| --- | --- |
| `init` | Create the notes folder, this month's page, and the dashboard |
| `context add\|remove\|default` | Manage the context registry |
| `contexts` | List contexts with month and open-task counts |
| `vault` | Resolved paths and statistics |
| `page` | Print a month page, or `--path` for just its path |
| `task` | Add a checklist item; prints the new id |
| `tasks` | List checklist items, filtered |
| `done` / `undone` | Tick a task off, or reopen it |
| `note` | Append a timestamped note to the month's log |
| `search` | Find notes and tasks |
| `digest` | Summarise a period, per context |
| `rollover` | Carry open tasks into the next month |

Full detail in [`docs/ptmutils.md`](./docs/ptmutils.md).

## Configuration

Everything is optional. `ptm.env` is discovered from the current directory
upwards, then next to the module, then `~/.config/ptm/ptm.env`:

```ini
PTM_CONTEXTS_FILE=~/.config/ptm/contexts.yaml
PTM_DEFAULT_CONTEXT=nf
PTM_NOTES_DIR=notes
```

The context registry is YAML, managed by `ptmutils context`:

```yaml
default: nf
contexts:
  nf:
    name: Work
    vault: ~/Documents/vaults/work
```

Never commit a real `ptm.env` — only `ptm.env.example`.

## Develop

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .
uv pip install --python .venv/bin/python pytest ruff

.venv/bin/python -m pytest
.venv/bin/ruff format src tests
.venv/bin/ruff check .
```

The project is **spec-driven**: [`src/ptm/specs.md`](./src/ptm/specs.md) is the
source of truth for behaviour and for the on-disk page format. Update it before
the code. See [`AGENTS.md`](./AGENTS.md) for the full conventions.

## Layout

```
ptm-utils/
├── AGENTS.md / CLAUDE.md      # agent instructions
├── install.sh                 # install/upgrade the CLI + link skills
├── ptm.env.example            # optional config template
├── docs/
│   ├── ptmutils.md            # command reference
│   └── vault_layout.md        # the Obsidian side: pages, Dataview, dashboard
├── skills/                    # ptm-capture, ptm-review, ptm-plan-day, ptm-monthly-rollover
├── src/ptm/
│   ├── ptmutils.py            # the whole CLI
│   └── specs.md               # THE SPEC
├── tests/test_ptmutils.py
└── .tech-specs/               # one file per piece of work
```

## License

[MIT](./LICENSE)

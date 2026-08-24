# AGENTS.md — Coding Agent Instructions

`ptm-utils` is a personal task-management toolset: a single Python CLI,
`ptmutils`, that reads and writes plain Markdown inside Obsidian vaults. One
vault per **context** (work, private, …), one Markdown page per **month** inside
it, with checklist tasks in a `## Tasks` section and timestamped notes in a
`## Log` section. It is fully offline — no credentials, no network calls, no
external service. Issue trackers are deliberately out of scope; a separate tool
covers those, and this repo does not duplicate it.

The Markdown files are the only state. There is no database and no index, so
every read must tolerate a human having edited the file by hand in Obsidian.

## Branching & Versioning

- Single long-lived branch: `master`. There is no release branch and no deploy.
- Branch for work: `git checkout -b feature/short-description origin/master`.
- Flow: branch from `master` → PR into `master`.
- The version lives ONLY in `pyproject.toml` (`[project].version`) — single
  source of truth, mirrored nowhere else.
- Versions are `MAJOR.MINOR.PATCH`. Bump PATCH for fixes, MINOR for new
  commands or options, MAJOR for a page-format change that needs a migration.

### Hard rules

- NEVER push directly to `master` — open a PR.
- Edit the version in `pyproject.toml` ONLY; never hardcode it elsewhere.
- NEVER change the page format contract in `src/ptm/specs.md` without a
  deliberate, documented migration — existing vaults hold real data.

## Build / Run / Test Commands

```bash
# Set up a dev environment (Python 3.11+ required)
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .
uv pip install --python .venv/bin/python pytest ruff pre-commit

# Install or upgrade the CLI for real use (also links the agent skills)
./install.sh
./install.sh --check          # verify, change nothing

# Run everything
.venv/bin/python -m pytest

# Run one file / one test
.venv/bin/python -m pytest tests/test_ptmutils.py
.venv/bin/python -m pytest tests/test_ptmutils.py::test_rollover_moves_open_tasks_and_leaves_done_ones_behind

# Lint and format
.venv/bin/ruff format src tests
.venv/bin/ruff check .

# Run the CLI from the checkout without installing
.venv/bin/ptmutils --help
```

## Tech Stack

| Piece | Choice |
| --- | --- |
| Language | Python 3.11+ |
| CLI | `argparse`, subcommands, no third-party CLI framework |
| Config | `PyYAML` for the context registry, `python-dotenv` for `ptm.env` |
| Storage | Plain Markdown files in Obsidian vaults — no database |
| Lint / format | `ruff` (line length 88, double quotes) |
| Tests | `pytest` |
| Packaging | `setuptools`, `src/` layout, one console script |

Runtime dependencies are deliberately minimal. Adding one needs a reason
stronger than convenience — this tool must keep working on any machine with a
Python and a folder.

## Project Structure

```
ptm-utils/
├── AGENTS.md                 # this file — the canonical agent instructions
├── CLAUDE.md                 # thin pointer to this file
├── README.md                 # human-facing overview and quick start
├── install.sh                # installs the CLI + links skills; re-run to upgrade
├── ptm.env.example           # optional config template (never commit a real ptm.env)
├── pyproject.toml            # deps, console script, ruff and pytest config
├── docs/
│   ├── ptmutils.md           # full command reference
│   └── vault_layout.md       # the Obsidian side: pages, Dataview, dashboard
├── skills/                   # agent skills, symlinked into ~/.claude/skills by install.sh
│   ├── ptm-capture/          # "add this as a task/note"
│   ├── ptm-review/           # "what's open?", "review my month"
│   ├── ptm-plan-day/         # "plan my day"
│   └── ptm-monthly-rollover/ # end-of-month close and carry-over
├── src/ptm/
│   ├── ptmutils.py           # the whole CLI — one self-contained module
│   └── specs.md              # THE SPEC: page format, commands, contracts
├── tests/
│   └── test_ptmutils.py      # unit + end-to-end against throwaway vaults
└── .tech-specs/              # one Markdown file per piece of work
```

## Spec-driven workflow

This project is **spec-driven**. `src/ptm/specs.md` is the source of truth for
the CLI's behaviour and for the on-disk page format. For any behaviour change:

1. **Read `src/ptm/specs.md` first, then update it first** — describe the
   intended behaviour, commands, options and output before writing code.
2. **Implement** `src/ptm/ptmutils.py` to match the updated spec.
3. **Sync the reference docs** in `docs/` in the same change.
4. **Add a Changelog row** at the bottom of `specs.md`.

Never change observable behaviour without updating `specs.md` in the same
change — if code and spec disagree, that is a bug.

The contracts in the spec are **stable**: the page frontmatter keys, the
`## Tasks` / `## Log` section headings, the `[key:: value]` inline-field form,
the `[ ]` / `[x]` / `[>]` checkbox states, the `t-xxxxx` id shape, and the
rollover semantics. Real vaults on disk depend on all of them.

## Code Style & Conventions

### General

- Target Python 3.11+. Modern syntax is fine, but match the surrounding style —
  the module uses `typing.Optional` / `List` / `Dict`, so keep new code
  consistent with it.
- Line length 88, double quotes, `ruff format` decides the rest.
- Import grouping is `ruff`'s isort with `ptm` and `tests` as first-party.
- Type-annotated signatures. Docstrings on anything non-obvious; skip them on
  short private helpers whose name already says it.

### CLI design

- One subcommand = one `cmd_*` function taking `(args, config)` and returning an
  exit code. Register it in `build_parser()`; keep `main()` thin.
- Every read command supports `--json`; every write command supports
  `--dry-run`. Add both when adding a command.
- Context selection goes through `Config.selection(slug, every)` — never reach
  into `config.contexts` directly from a command.
- User-facing failures raise `PtmError`. Anything else is a bug and should
  trace.
- Human output is plain, greppable text: no status icons, no colour, fixed-width
  columns.

### Reading and writing pages

- All page edits go through `edit_page()`, which holds an exclusive `flock`.
  Never open a page file for writing directly.
- Parsers must tolerate hand-edited files: unknown lines are ignored, never
  rejected and never rewritten.
- Only `done`, `undone` and `rollover` may modify an existing line. Everything
  else appends.
- Never write anywhere in a vault other than `notes/YYYY-MM.md` and
  `_ptm_dashboard.md`.

<!-- nf:code-comments v1 — managed by nf-init-project -->
## Code comments

**Make the code explain itself; comment only what the code cannot say.**

A comment is a liability: nothing verifies it, and it silently goes stale the
first time someone changes the code beside it. A good name or a small extracted
function carries the same meaning and cannot drift. Reach for the comment last.

Before writing a comment, try in this order:

1. **Rename.** `retry_after_seconds` instead of `t` plus a comment saying what
   `t` holds. `is_eligible_for_refund` instead of a comment explaining the
   condition.
2. **Extract.** Pull the block into a well-named function or a named
   intermediate variable. A comment introducing a ten-line block usually means
   that block wants to be a function whose name is that comment.
3. **Restructure.** Early return instead of `# happy path continues here`.
   A dataclass/enum/type instead of `# keys: id, name, status`.

Only then write the comment.

### Comment the *why*, never the *what*

The diff shows what changed; the code shows what it does. A comment earns its
place when it records something not recoverable from reading the code:

- a non-obvious constraint (an upstream API caps the page size at 100)
- a deliberate trade-off, and what was rejected
- a workaround, with what breaks without it
- a correctness trap the next reader would otherwise "clean up"

```python
# The vendor's cursor expires after 60s, so re-page from scratch rather than
# resuming — resuming silently returns a truncated result set.
```

### Do not write

- **Narration** — `# loop over the users`, `# increment the counter`,
  `# return the result`.
- **Section dividers** — `# --- helpers ---`, `# Step 1: validate`. If a
  function needs internal chapters, it wants to be several functions.
- **Signature restatement** — a docstring that only re-lists the parameters and
  their types with no added meaning.
- **Change narration** — `# added validation`, `# updated to use the new API`,
  `# was previously a list`. That belongs in the commit message; the code is
  read by people who will never see this change in isolation.
- **Commented-out code.** Delete it — git remembers.
- **`TODO` without an owner and a condition.** `# TODO: make this faster` is
  noise; `# TODO: drop this fallback once every client sends the header` is a
  real note.

### Docstrings are different

Docstrings are API documentation, not commentary, and this repo's style section
governs them. Write one for anything another module calls — what it does, what
it returns, what it raises — and skip it for a short private helper whose name
already says it. Follow the format the surrounding code already uses.

### Reviewing your own output

Before finishing a change, reread the diff and delete every comment that only
restates the line below it. Density is the tell: several comments in one short
function almost always means the function needs better names or splitting, not
better comments.
<!-- /nf:code-comments -->

## Testing conventions

- Tests live in `tests/`, mirroring the module they cover.
- The `vaults` fixture registers two contexts against `tmp_path` vaults and
  returns a `run(*argv)` helper that drives `main()` and returns stdout. Prefer
  it over touching files directly — it exercises the real argument parsing and
  the real writes.
- A test that asserts on the page format is asserting a **contract**. If one
  fails, check `specs.md` before "fixing" the test.
- Never let a test write outside `tmp_path`. The `vaults` fixture points
  `XDG_CONFIG_HOME` and `DEFAULT_CONFIG_DIR` at the temp tree for exactly this
  reason.
- New commands need at least: a happy path, a `--json` shape assertion, and a
  `--dry-run` "writes nothing" test.

## Configuration & secrets

- All configuration is read from `ptm.env` via `python-dotenv` + `os.environ`,
  plus the YAML context registry. Never hardcode paths, vault locations or
  context names.
- Never commit a real `ptm.env` — only `ptm.env.example` with placeholders.
- There are no credentials in this project and there should never be any. If a
  feature seems to need one, it belongs in a different tool.
- Manage dependencies in `pyproject.toml`. Do not create a `requirements.txt`.

## Do NOT

- Do NOT write anywhere in a user's vault except `notes/YYYY-MM.md` and
  `_ptm_dashboard.md`.
- Do NOT delete or rewrite a note entry — the tool appends; humans edit in
  Obsidian.
- Do NOT change the page format, the checkbox states or the task-id shape
  without updating `specs.md` and considering existing vaults.
- Do NOT add a network call, a credential, or an issue-tracker integration.
- Do NOT hardcode configuration values — use `ptm.env` or the context registry.
- Do NOT commit secrets, `.env` files, or credentials.
- Do NOT skip `ruff check` and the tests before committing.
- Do NOT narrate code with comments — rename, extract, or restructure so the
  code reads on its own, and keep comments for the *why*.
- Do NOT create commits or push unless explicitly asked.

## Key references

- [`src/ptm/specs.md`](./src/ptm/specs.md) — the behaviour and page-format contract
- [`docs/ptmutils.md`](./docs/ptmutils.md) — full command reference
- [`docs/vault_layout.md`](./docs/vault_layout.md) — the Obsidian side
- [`skills/`](./skills) — the agent skills that drive the CLI

## Documentation

AI-generated docs must include this header:

> 📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

Documentation filenames: lowercase with underscores (`my_documentation.md`).

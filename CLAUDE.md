# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Full coding agent instructions are in [`AGENTS.md`](./AGENTS.md). Key points are summarized below.

## Project Overview

`ptm-utils` is a personal task-management toolset: one Python CLI, `ptmutils`,
that reads and writes plain Markdown inside Obsidian vaults. One vault per
**context** (work, private, …), one page per **month** inside it, with checklist
tasks in a `## Tasks` section and timestamped notes in a `## Log` section.
Fully offline — no credentials, no network, no issue-tracker integration.

## Commands

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .

.venv/bin/python -m pytest                 # all tests
.venv/bin/python -m pytest tests/test_ptmutils.py::test_digest_counts_work_per_context
.venv/bin/ruff format src tests
.venv/bin/ruff check .

./install.sh                               # install/upgrade the CLI + link skills
./install.sh --check                       # verify, change nothing
```

## Project Structure

- `src/ptm/ptmutils.py` — the entire CLI, one self-contained module
- `src/ptm/specs.md` — **the spec**: page format, commands, contracts
- `skills/ptm-*/SKILL.md` — agent skills that drive the CLI
- `docs/` — human reference; `tests/` — pytest, end-to-end against temp vaults

## Key Patterns

- One subcommand = one `cmd_*(args, config)` function, registered in `build_parser()`.
- Context selection always goes through `Config.selection(slug, every)`.
- Every page write goes through `edit_page(path, mutate)` — it holds an `flock`.
- User-facing failures raise `PtmError`; `main()` prints `error: …` and exits 1.
- Parsers must tolerate hand-edited Markdown: ignore what you don't recognise,
  never rewrite it.
- Every read command takes `--json`; every write command takes `--dry-run`.

## Workflow

- Read `src/ptm/specs.md` before implementing; update it **first**, then the code,
  then `docs/`, and add a Changelog row.
- Run `.venv/bin/ruff check .` and `pytest` after significant changes.
- Write self-documenting code: prefer a better name or an extracted function over
  a comment, and comment only what the code cannot say (see `AGENTS.md` §
  "Code comments").
- Do not create commits unless explicitly asked.
- Do not push to remote unless explicitly asked.

## Do NOT

- Do NOT write anywhere in a user's vault except `notes/YYYY-MM.md` and `_ptm_dashboard.md`.
- Do NOT change the page format, checkbox states, or task-id shape without
  updating `specs.md` and thinking about existing vaults.
- Do NOT add a network call, a credential, or a Jira/Confluence integration.
- Do NOT delete or rewrite a note entry — append, and let the human edit in Obsidian.

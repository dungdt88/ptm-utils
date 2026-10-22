# Yearly goals

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

## Problem

Every year the user writes a short plan, usually under ten goals, and keeps it
for the whole year. In Notion this was a database. Each row had a status
(Not started / In progress / Done) and a tag, and each row's page held a
description, a checklist of milestones and dated comments recording progress.
The plan has to move into Obsidian with the basics intact. The user wants both a
plain-Obsidian way of working and CLI and agent support, in **both** the work
and the personal vault.

## Options considered

| Option | Verdict |
| --- | --- |
| **Obsidian Bases** over one note per goal | **Chosen.** It is a core plugin, so nothing extra needs installing. It is a live table over frontmatter properties with inline editing, the closest match to a Notion database. |
| Dataview `TABLE` over the same notes | Read-only results, and it needs a community plugin. Kept only for the dashboard, which already depends on Dataview and can count checkboxes, which Bases cannot. |
| One `goals/2026.md` page with a section per goal | Fits the month-page model, but there is no table and no per-goal page, and a long page is awkward to scan. Rejected. |
| Goals as tasks on the month pages | Wrong lifetime: rollover would forward them every month. Rejected. |
| Bases community plugins (Custom Selectors, Power Bases) for coloured status pills | Optional polish the user can add. The format does not depend on them. |

## Shape

- `goals/YYYY/<Title>.md`, with frontmatter `type`, `id` (`g-xxxxx`),
  `status`, `area`, `created`, and the sections `## Description`,
  `## Milestones` and `## Progress` (`- YYYY-MM-DD — text`).
- `goals/YYYY.base` holds two table views, *Goals* and *By status*. Last edited
  is `file.mtime`, so there is no `updated:` property to drift out of date.
- `goals/_templates/goal.md` is for the Templates core plugin, for goals created
  by hand.
- Commands: `goal init|add|show|log|status|milestone|check|uncheck` and `goals`.
- There is no carry-over between years. The user decides what to bring forward.
  The `ptm-year-plan` skill walks them through that decision.
- A goals section on `_ptm_dashboard.md`. Only new dashboards (or
  `init --force`) get it.

## Decisions worth remembering

- **The folder is the year, and every `.md` in it is a goal.** The CLI and the
  Bases view then always agree, even for notes created by hand without
  frontmatter.
- **Frontmatter is edited line by line.** Re-serialising the YAML would reorder
  properties and reformat the ones the user added in Obsidian.
- **Logging progress moves `not-started` to `in-progress`.** Recording progress
  is what starting a goal means. No other status change happens implicitly.
- **Goals are addressed by id or by title.** Title matching is limited to one
  year, so a goal brought forward does not become ambiguous with its old note.

## Testing

`tests/test_ptmutils.py`, § Goals: a happy path for each subcommand, `--json`
shapes, `--dry-run` writing nothing (`add`, `log`, `init`), refusal to
overwrite, ambiguous lookups, year scoping, hand-made notes without
frontmatter, and `init` keeping customised files.

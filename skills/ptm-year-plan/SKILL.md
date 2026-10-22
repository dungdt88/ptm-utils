---
name: ptm-year-plan
description: >-
  Use when the user wants to write a year's goals into their vaults — "plan my
  2027 goals", "set my new year resolutions", "lên kế hoạch năm mới", "start next
  year's checklist". Reads last year's goals with `ptmutils goals`, walks through
  them so the user decides which to bring forward, collects the new ones in the
  user's own words, previews every goal with `--dry-run`, then creates the
  year's folder, Bases table and goal notes with `ptmutils goal init` and
  `ptmutils goal add` in the right vault (work or personal). Never invents a goal
  or a milestone.
---

# Write a year's goals

A year's plan is a handful of goals, usually fewer than ten, kept as one note
each in `goals/YYYY/` in each vault. Obsidian shows them as a table
(`goals/YYYY.base`). This skill helps the user write that set at the turn of the
year.

The defining rule: **the plan is the user's.** You ask, list and write things
down. You do not suggest resolutions, split a goal into milestones nobody
mentioned, or decide which of last year's goals deserve another year.

## Workflow

### 1. Fix the year and the vaults

```bash
ptmutils contexts
```

The target year is the one the user names. If they don't name one, it is next
year from mid-November onward and this year before that. Confirm it in one line.

Goals live in the vault they belong to: work goals in the work context, personal
and family ones in the personal context. Ask if it is unclear.

### 2. Look back at last year, if it exists

```bash
ptmutils goals --all --year <last year> --json
```

Show it compactly, per context: done / in progress / not started, with the
milestone count and the last progress date. Then go through **only the goals
that are not done**, one at a time, and ask: *bring it into <year>, or leave
it?* Nothing carries over unless the user says so. A goal that is brought
forward is added again as a fresh note, so its old note stays as last year's
record.

Ask whether to copy an unfinished goal's open milestones too. Copy them only if
the user says yes.

### 3. Collect the new goals

For each goal, ask for:

| Field | Note |
| --- | --- |
| Title | The user's wording. A `[Mika]`-style prefix becomes the area. |
| Area | One label: `family`, `personal`, a company name. Optional. |
| Description | Why it matters, or what "done" looks like. Optional. |
| Milestones | Only the ones the user lists. Zero is fine. |
| Vault | Work or personal, from step 1. |

Keep going until the user says that's all.

### 4. Preview

Print the whole plan grouped by vault, then dry-run one goal so the user sees the
exact note:

```bash
ptmutils goal add "Plan for living abroad" -c priv --year 2027 --area family \
  --description "Decide by summer whether we move" \
  --milestone "Shortlist cities" --milestone "Visit schools" --dry-run
```

Do not write anything until the user approves.

### 5. Write

```bash
ptmutils goal init -c priv --year 2027      # folder, table, template; idempotent
ptmutils goal add "…" -c priv --year 2027 --area family --milestone "…"
```

Run one `goal add` per goal and collect the ids it prints. If a title already
exists in that year, the command fails and nothing is overwritten. Tell the user
and ask how they want to name it.

### 6. Report

```
[Personal] 2027 — 4 goals
  g-4be07  Plan for living abroad          family   2 milestones
  g-91c2e  Start creating robots           family   0 milestones
  …
Table: ~/Documents/vaults/personal/goals/2027.base
```

Mention once that progress is logged with `ptmutils goal log <goal> "…"`, or by
adding a dated line under `## Progress` in Obsidian.

## Hard rules

- **Never invent a goal, an area, a description or a milestone.** Empty is a
  valid answer.
- **Never carry a goal over automatically.** Each one is the user's call.
- **Never edit last year's goal notes.** They are the record of that year.
- **Preview before writing**, and write to the vault the user confirmed.

## Related

- `ptm-capture`: log progress on a goal during the year
- `ptm-review`: "how are my goals doing?"

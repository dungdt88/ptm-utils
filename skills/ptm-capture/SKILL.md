---
name: ptm-capture
description: >-
  Use when the user wants something written into their personal task-management
  vault — "add a task", "note this down", "remind me to …", "ghi chú lại", "log
  this to my notes". Turns loose conversation into well-formed entries on the
  right month page of the right context: checklist items via `ptmutils task`,
  timestamped notes via `ptmutils note`. Decides task-vs-note from what the thing
  actually is, picks the context from the conversation and confirms when it is
  ambiguous, and never invents work the user did not describe.
---

# Capture into the personal task vault

This skill turns "oh, I need to sort out that redirect bug" into a real
checklist item on the right page, without the user leaving the terminal.

The defining rule: **capture what the user said, not what you infer they meant.**
Splitting one sentence into six speculative subtasks is the failure mode here.
One thing said, one thing captured.

> **Portability:** the only dependency is the `ptmutils` CLI. If it is not
> installed, fall back to editing the Markdown page directly (§5) — the format
> is fixed and simple. Never block on the tool being missing.

## Workflow

### 1. Find the contexts before writing

```bash
ptmutils contexts
```

This lists every registered context, which is the default, and how many open
tasks each has. If nothing is registered, tell the user to run
`ptmutils context add <slug> --vault <path>` — do not guess a vault path.

### 2. Decide: task or note

| It is a **task** when | It is a **note** when |
| --- | --- |
| It is something to *do* | It is something that *happened* or was *decided* |
| It can be finished | It is context you'll want in six months |
| "I need to…", "remind me…", "don't forget…" | "we agreed…", "turns out…", "the reason is…" |

Both, sometimes: a meeting produces a note *and* the actions from it. Capture
both; do not force one into the other.

### 3. Pick the context

In order of preference:

1. **The user said it** — "add to my private list", "for the work vault".
2. **The conversation makes it obvious** — you are in a work repo, the subject is
   a work system, and one context clearly matches.
3. **Ask.** One short question with the registered slugs as options. Do not
   default to the default context on a coin-flip.

A task on the wrong page is worse than a five-second question.

### 4. Write it

**A task:**

```bash
ptmutils task "Fix the password-reset redirect" -c nf --due 2026-08-30 --prio high
```

- **Text**: the user's own words, tidied into an imperative. Keep their nouns —
  they are how they will search for it later.
- `--due` only when a date was actually stated or clearly implied ("by Friday",
  "before the release"). Never invent a deadline.
- `--prio high` only when the user signalled urgency. Most tasks have no
  priority, and that is correct.
- `--month` only when the user means a future month. Default is this month.
- Report the returned id back to the user — it is how they check it off.

**A note:**

```bash
ptmutils note --title "Sprint planning" -c nf \
  --body "Decided to defer the search rewrite to September." \
  --detail "Blocked on an upstream release; revisit in the first week of September"
```

- **Title**: one line, specific. "Sprint planning" beats "Meeting".
- **Body**: the summary someone would quote in a standup.
- **Details**: the things worth recalling months later — decisions, gotchas,
  what was rejected and why. This is where the value is.
- `--date yesterday` when the user is recording something from an earlier day.

**Several things at once?** One command each. Batch them in a single message,
then report the whole set.

### 5. Fallback when `ptmutils` is missing

Find the vault, open `notes/YYYY-MM.md`, and edit it directly:

- A task goes at the end of the `## Tasks` section:
  `- [ ] Text [id:: t-xxxxx] [added:: YYYY-MM-DD]` (any unused 5-hex id)
- A note goes at the end of `## Log`, under a `### YYYY-MM-DD (Ddd)` heading,
  as `#### HH:MM — Title` followed by the body.

The format is documented in `docs/vault_layout.md`.

### 6. Confirm what you wrote

Report back compactly — id, text, context, page — so the user can see it landed
where they expected:

```
t-da621  Fix the password-reset redirect   [Work 2026-08, due 2026-08-30]
```

Use `--dry-run` first whenever you are unsure about the wording or the context;
it prints the exact Markdown line without writing it.

## Hard rules

- **Never invent work.** No speculative subtasks, no "you'll probably also
  need to…". If the user said one thing, capture one thing.
- **Never invent a due date or a priority.** Absent is a valid value.
- **Never guess a context** when two plausibly fit — ask.
- **Never edit or delete an existing note entry.** Add a new one.
- **Never write outside `notes/YYYY-MM.md`** in the vault.
- Keep the user's own words. You are transcribing, not drafting.

## Related

- `ptm-review` — read the vault back
- `ptm-plan-day` — pick today's shortlist from what is open
- `ptm-monthly-rollover` — close a month and carry the rest forward

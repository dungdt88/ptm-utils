---
name: ptm-plan-day
description: >-
  Use when the user wants a plan for today or tomorrow from their personal task
  vault — "plan my day", "what should I work on", "lên kế hoạch hôm nay", "what's
  on for tomorrow". Reads open tasks across every context with `ptmutils tasks`,
  proposes a short realistic shortlist weighted by due date, priority and how
  long things have been carried, confirms it with the user, then records the
  agreed plan as a dated note with `ptmutils note`. Picks from what exists; it
  never invents tasks to fill a day.
---

# Plan the day from the task vault

This skill turns a list of open tasks into a decision about today. Two things
make it useful rather than decorative: it is **short** (a day holds three or four
real things, not eleven), and it is **honest about capacity** (it asks what else
is already in the day before proposing anything).

## Workflow

### 1. Read what is open, everywhere

```bash
ptmutils tasks --all --json
```

Every context, always — a personal errand with a deadline today outranks a work
task due next week, and the user cannot see that if you only read one vault.

### 2. Ask what the day already holds

Before proposing anything:

> How much of today is already committed — meetings, anything fixed?

You cannot plan a day you don't know the shape of. If they say "half of it's
meetings", the shortlist is two items, not five. Ask once, briefly; if they
don't answer, assume a normal day and say that you did.

### 3. Rank

Weight, in order:

1. **Overdue** — `due` before today.
2. **Due today or tomorrow.**
3. **`prio:: high`** with a near date.
4. **Carried tasks** (`from::` present) — these have already lost a month.
   Either today is the day, or they should be dropped. Surface one, not all.
5. Everything else.

Then cut. **Three to five items.** A shortlist that cannot fail is worth more
than a complete list that will. If a task is obviously bigger than a day, say so
and propose the first concrete slice of it rather than the whole thing.

Spread across contexts when the user has more than one live: an all-work plan on
a day with an overdue personal deadline is a bad plan.

### 4. Propose, then confirm

```
Plan for Mon 2026-08-24 — 4 things

  [Work]
    t-da621  Fix the password-reset redirect        OVERDUE (due 20 Aug), high
    t-9f102  Write the release notes                 due Thu
  [Personal]
    t-939db  Renew passport                          carried from July

  Also open, not on the list: 7 tasks — say the word if something's missing.
```

Always show what you left out, as a count. The user knows things you do not, and
the omission is the part they will want to correct.

Wait for confirmation. Adjust as asked.

### 5. Record the agreed plan

Once the user agrees, write it as a note in their **primary work context** (ask
which, once, if it is not obvious), so the day is on the record:

```bash
ptmutils note --title "Plan for the day" -c nf \
  --body "Fix the password-reset redirect; write the release notes; renew passport." \
  --detail "t-da621 — overdue, do first" \
  --detail "t-9f102 — due Thursday" \
  --detail "t-939db — carried from July, personal"
```

Use `--date tomorrow` when planning ahead.

Do **not** create new tasks for the plan. The tasks already exist; the plan is a
note that points at them by id.

### 6. Close the loop later

If the user comes back with "done with the redirect", close it:

```bash
ptmutils done t-da621
```

## Hard rules

- **Never invent a task to fill the day.** The plan is drawn from what is
  already in the vault. If it is nearly empty, say so — that is information.
- **Never propose more than five.** If the user wants more, they will ask.
- **Never silently drop a context.** Read `--all`, and say what you left out.
- **Never write the plan before the user agrees to it.**
- **Do not duplicate tasks into the note** as new checklist items — reference
  their ids.

## Related

- `ptm-review` — the fuller "where am I" picture
- `ptm-capture` — add whatever comes up during the day
- `ptm-monthly-rollover` — end-of-month close and carry-over

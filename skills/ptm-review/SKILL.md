---
name: ptm-review
description: >-
  Use when the user wants to see their personal task vault read back — "what's
  open?", "what's overdue?", "review my month", "what did I get done in August",
  "còn việc gì chưa xong". Reads open tasks and the month's log across one or all
  contexts with `ptmutils tasks` and `ptmutils digest`, then presents a grouped,
  prioritised picture: what is overdue, what is due soon, what has gone stale,
  and what actually got finished. Read-only by default — it proposes changes and
  asks before writing anything.
---

# Review the personal task vault

This skill answers "where am I?" It reads, groups and interprets — it does not
tidy up on its own. The user asked what the state *is*; changing that state
without asking makes the answer untrustworthy.

## Workflow

### 1. Establish scope

```bash
ptmutils contexts
```

Then decide what the user meant:

| They said | Scope |
| --- | --- |
| "what's open?" | every context (`--all`) |
| "what's open for work?" | that context (`-c nf`) |
| "review my month" | the current month, every context |
| "how was August?" | `--month 2026-08` |

When in doubt, go wider — `--all`. An extra context in the output costs a line;
a missing one costs a missed deadline.

### 2. Read

```bash
ptmutils tasks --all --json
ptmutils digest --all --json
```

Use `--json`. You are going to regroup and re-sort the data, so take the
structured form rather than parsing the human output.

For a specific past period:

```bash
ptmutils digest --all --month 2026-08 --json
ptmutils digest --all --since 2026-07-01 --until 2026-07-31 --json
```

### 3. Interpret before you print

Raw output is not a review. Sort what you got into buckets that mean something:

| Bucket | Rule |
| --- | --- |
| **Overdue** | `due` is before today |
| **Due soon** | `due` within 7 days |
| **Stale** | `added` more than ~30 days ago, still open, no due date |
| **Carried** | has `from::` — it has already survived a rollover |
| **No date** | everything else |

**Carried and stale together is the signal worth naming.** A task that has been
forwarded twice and has no due date is not a task the user is going to do; it is
a decision they have not made. Say so, once, without nagging.

### 4. Present

Group by **context first**, then by bucket. Lead with what is actionable.

```
[Work] — 6 open

  Overdue
    t-da621  Fix the password-reset redirect        due 2026-08-20  high
  Due this week
    t-9f102  Write the release notes                 due 2026-08-27
  Carried from July, still no date
    t-3c8f0  Rewrite the search index                      carried 2×

[Personal] — 2 open
  ...
```

Keep it plain text: no status icons, fixed-width columns, greppable. Show the
id — it is what the user types to close something.

For "what did I get done", lead with the **done** list from the digest and keep
the open list short; that is a different question.

### 5. Offer, do not act

End with concrete suggestions tied to real ids, and let the user choose:

- "`t-3c8f0` has been carried twice with no due date — drop it, or give it a
  date?"
- "Three tasks are overdue in Work. Want me to close any of them?"

Only run `ptmutils done`, `undone` or `rollover` when the user says so. The one
exception is an explicit instruction in the same breath ("review my month and
close anything I've already finished") — and even then, list what you are about
to close first.

## Hard rules

- **Read-only unless asked.** Never close, reopen or move a task on your own
  judgement.
- **Never re-summarise the vault into a new note** unless the user asks — that
  is `ptm-capture`'s job, and duplicating state is how it rots.
- **Report emptiness honestly.** "No open tasks in Private" is a useful answer;
  padding it out is not.
- **Do not moralise** about overdue work. Show it, name the pattern once, move
  on.

## Related

- `ptm-capture` — write into the vault
- `ptm-plan-day` — turn what is open into today's shortlist
- `ptm-monthly-rollover` — close the month and carry the rest forward

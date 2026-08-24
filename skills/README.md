# Agent skills

📝 Note: This documentation is generated or assisted by AI, but all changes require human review before being committed.

Each folder here is an agent skill: a `SKILL.md` telling an AI agent how to drive
`ptmutils` for one job. `./install.sh` symlinks them into `~/.claude/skills/`
(or `~/.agents/skills/` with `--universal`), so they work from any repo.

| Skill | Use it when |
| --- | --- |
| [`ptm-capture`](./ptm-capture/SKILL.md) | "add a task", "note this down", "remind me to…" |
| [`ptm-review`](./ptm-review/SKILL.md) | "what's open?", "what's overdue?", "review my month" |
| [`ptm-plan-day`](./ptm-plan-day/SKILL.md) | "plan my day", "what should I work on" |
| [`ptm-monthly-rollover`](./ptm-monthly-rollover/SKILL.md) | "close out August", "roll over to September" |

They share three principles:

1. **Capture what was said, not what was inferred.** No speculative subtasks, no
   invented deadlines.
2. **Read wide, write narrow.** Read across every context by default; write to
   exactly one, and confirm which when it is ambiguous.
3. **Preview before moving anything.** `--dry-run` first, approval second, write
   third.

## Writing a new one

Follow the shape of the existing four: YAML frontmatter with `name` and a
`description` that says *when to use it* (that is what an agent matches on),
then a numbered workflow, then hard rules. Keep the CLI calls copy-pasteable and
real — check them against [`docs/ptmutils.md`](../docs/ptmutils.md).

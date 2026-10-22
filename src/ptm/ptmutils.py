#!/usr/bin/env python3
"""ptmutils — personal task management on top of Obsidian vaults.

One vault per context, one Markdown page per month inside it. Notes are appended
to a dated log; checklist items live in a single Tasks section so the month's
open work is visible in one place. Yearly goals live beside the months, one note
per goal, in a folder per year.

See ``specs.md`` next to this file for the page-format contract.
"""

import argparse
import calendar
import fcntl
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Page format contract — see specs.md. Changing any of these is a migration.
# --------------------------------------------------------------------------- #

PAGE_TYPE = "ptm-month"
TASKS_HEADING = "## Tasks"
LOG_HEADING = "## Log"
DEFAULT_NOTES_DIR = "notes"
DEFAULT_GOALS_DIR = "goals"
DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")) / "ptm"

TASK_RE = re.compile(r"^(?P<indent>[ \t]*)- \[(?P<box>.)\] (?P<rest>.*)$")
FIELD_RE = re.compile(r"\[(?P<key>[A-Za-z_][\w-]*)::\s*(?P<value>[^\]]*)\]")
DAY_RE = re.compile(r"^### (?P<date>\d{4}-\d{2}-\d{2})\b")
ENTRY_RE = re.compile(r"^#### (?P<time>\d{1,2}:\d{2})\s+[—–-]\s+(?P<title>.+)$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
YEAR_RE = re.compile(r"^\d{4}$")

GOAL_TYPE = "ptm-goal"
GOAL_STATUSES = ("not-started", "in-progress", "done")
GOAL_TEMPLATE = Path("_templates") / "goal.md"
DESCRIPTION_HEADING = "## Description"
MILESTONES_HEADING = "## Milestones"
PROGRESS_HEADING = "## Progress"
PROGRESS_RE = re.compile(r"^- (?P<date>\d{4}-\d{2}-\d{2})\s+[—–-]\s+(?P<text>.+)$")
# Characters Obsidian refuses in a file name, plus those that break [[links]].
UNSAFE_TITLE_RE = re.compile(r'[\\/:*?"<>|#^\[\]]')
PLAIN_YAML_RE = re.compile(r"^[\w][\w .-]*$")

# Obsidian renders `[>]` as "forwarded"; Dataview does not count it as complete.
BOX_OPEN = " "
BOX_DONE = "x"
BOX_MOVED = ">"

STATUS_BY_BOX = {BOX_OPEN: "open", "x": "done", "X": "done", BOX_MOVED: "moved"}


class PtmError(Exception):
    """A user-facing failure — reported without a traceback."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass
class Context:
    slug: str
    name: str
    vault: Path
    notes_dir: str = DEFAULT_NOTES_DIR
    goals_dir: str = DEFAULT_GOALS_DIR

    @property
    def notes_path(self) -> Path:
        return self.vault / self.notes_dir

    def page_path(self, month: str) -> Path:
        return self.notes_path / f"{month}.md"

    @property
    def goals_path(self) -> Path:
        return self.vault / self.goals_dir

    def goal_year_path(self, year: str) -> Path:
        return self.goals_path / year

    def goal_base_path(self, year: str) -> Path:
        return self.goals_path / f"{year}.base"

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "vault": str(self.vault),
            "notes_dir": self.notes_dir,
            "goals_dir": self.goals_dir,
        }


@dataclass
class Config:
    path: Path
    default_context: Optional[str]
    contexts: Dict[str, Context] = field(default_factory=dict)

    def resolve(self, slug: Optional[str]) -> Context:
        """Return the named context, or the default when none is named."""
        if not self.contexts:
            raise PtmError(
                "No contexts registered yet. Add one with:\n"
                "  ptmutils context add <slug> --vault ~/path/to/vault "
                '--name "Human Name"'
            )
        wanted = slug or self.default_context
        if not wanted:
            raise PtmError(
                "No context given and no default set. Pass --context, or set a "
                "default with: ptmutils context default <slug>"
            )
        key = wanted.lower()
        if key in self.contexts:
            return self.contexts[key]
        matches = [c for c in self.contexts.values() if c.name.lower() == key]
        if len(matches) == 1:
            return matches[0]
        known = ", ".join(sorted(self.contexts)) or "(none)"
        raise PtmError(f"Unknown context '{wanted}'. Known contexts: {known}")

    def selection(self, slug: Optional[str], every: bool) -> List[Context]:
        if every:
            return [self.contexts[k] for k in sorted(self.contexts)]
        return [self.resolve(slug)]

    def save(self) -> None:
        payload = {
            "default": self.default_context,
            "contexts": {
                slug: {
                    "name": ctx.name,
                    "vault": _collapse_home(ctx.vault),
                    **(
                        {"notes_dir": ctx.notes_dir}
                        if ctx.notes_dir != DEFAULT_NOTES_DIR
                        else {}
                    ),
                    **(
                        {"goals_dir": ctx.goals_dir}
                        if ctx.goals_dir != DEFAULT_GOALS_DIR
                        else {}
                    ),
                }
                for slug, ctx in sorted(self.contexts.items())
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "# ptmutils contexts — one Obsidian vault per context.\n"
            "# Edit by hand or with `ptmutils context add|remove|default`.\n"
            + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def _collapse_home(path: Path) -> str:
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home) :] if text.startswith(home) else text


def _find_env_file() -> Optional[Path]:
    """Locate ptm.env from the cwd upwards, then beside the script, then XDG."""
    candidates: List[Path] = []
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        candidates.append(base / "ptm.env")
        candidates.extend(parent / "ptm.env" for parent in base.parents)
    candidates.append(DEFAULT_CONFIG_DIR.expanduser() / "ptm.env")
    return next((c for c in candidates if c.is_file()), None)


def load_config() -> Config:
    env_file = _find_env_file()
    if env_file:
        load_dotenv(env_file, override=False)

    config_path = Path(
        os.environ.get("PTM_CONTEXTS_FILE", DEFAULT_CONFIG_DIR / "contexts.yaml")
    ).expanduser()

    contexts: Dict[str, Context] = {}
    default_context = os.environ.get("PTM_DEFAULT_CONTEXT")
    notes_dir_default = os.environ.get("PTM_NOTES_DIR", DEFAULT_NOTES_DIR)
    goals_dir_default = os.environ.get("PTM_GOALS_DIR", DEFAULT_GOALS_DIR)

    if config_path.is_file():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        default_context = default_context or raw.get("default")
        for slug, entry in (raw.get("contexts") or {}).items():
            entry = entry or {}
            vault = entry.get("vault")
            if not vault:
                raise PtmError(f"Context '{slug}' in {config_path} has no vault path.")
            contexts[slug.lower()] = Context(
                slug=slug.lower(),
                name=entry.get("name") or slug,
                vault=Path(str(vault)).expanduser(),
                notes_dir=entry.get("notes_dir", notes_dir_default),
                goals_dir=entry.get("goals_dir", goals_dir_default),
            )

    if default_context and default_context.lower() not in contexts:
        default_context = None
    if not default_context and len(contexts) == 1:
        default_context = next(iter(contexts))

    return Config(path=config_path, default_context=default_context, contexts=contexts)


# --------------------------------------------------------------------------- #
# Dates and months
# --------------------------------------------------------------------------- #


def parse_date(value: Optional[str]) -> date:
    """Accept YYYY-MM-DD, today, yesterday, tomorrow, or a -N day offset."""
    today = date.today()
    if not value or value == "today":
        return today
    if value == "yesterday":
        return today - timedelta(days=1)
    if value == "tomorrow":
        return today + timedelta(days=1)
    if re.fullmatch(r"[+-]\d+", value):
        return today + timedelta(days=int(value))
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise PtmError(f"Cannot read '{value}' as a date (use YYYY-MM-DD).") from exc


def month_of(day: date) -> str:
    return day.strftime("%Y-%m")


def shift_month(month: str, delta: int) -> str:
    year, mon = (int(part) for part in month.split("-"))
    index = (year * 12 + mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def parse_month(value: Optional[str], anchor: Optional[date] = None) -> str:
    """Accept YYYY-MM, this/current, last/prev, next, or a +/-N month offset."""
    current = month_of(anchor or date.today())
    if not value or value in ("this", "current"):
        return current
    if value in ("last", "prev", "previous"):
        return shift_month(current, -1)
    if value == "next":
        return shift_month(current, 1)
    if re.fullmatch(r"[+-]\d+", value):
        return shift_month(current, int(value))
    if MONTH_RE.fullmatch(value):
        return value
    raise PtmError(f"Cannot read '{value}' as a month (use YYYY-MM).")


def parse_year(value: Optional[str]) -> str:
    """Accept YYYY, this/current, last/prev, next, or a +/-N year offset."""
    current = date.today().year
    if not value or value in ("this", "current"):
        return str(current)
    if value in ("last", "prev", "previous"):
        return str(current - 1)
    if value == "next":
        return str(current + 1)
    if re.fullmatch(r"[+-]\d+", value):
        return str(current + int(value))
    if YEAR_RE.fullmatch(value):
        return value
    raise PtmError(f"Cannot read '{value}' as a year (use YYYY).")


def month_bounds(month: str) -> Tuple[date, date]:
    year, mon = (int(part) for part in month.split("-"))
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def month_title(month: str) -> str:
    first, _ = month_bounds(month)
    return first.strftime("%B %Y")


# --------------------------------------------------------------------------- #
# Page model
# --------------------------------------------------------------------------- #


@dataclass
class Task:
    id: str
    text: str
    status: str
    fields: Dict[str, str]
    context: str
    context_slug: str
    month: str
    line_no: int
    raw: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "context": self.context,
            "context_slug": self.context_slug,
            "month": self.month,
            **self.fields,
        }


@dataclass
class Note:
    date: str
    time: str
    title: str
    body: str
    details: List[str]
    tags: List[str]
    context: str
    context_slug: str
    month: str

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "time": self.time,
            "title": self.title,
            "body": self.body,
            "details": self.details,
            "tags": self.tags,
            "context": self.context,
            "context_slug": self.context_slug,
            "month": self.month,
        }


def strip_fields(text: str) -> Tuple[str, Dict[str, str]]:
    """Split ``text [key:: value]`` into its prose and its Dataview fields."""
    fields = {m.group("key"): m.group("value").strip() for m in FIELD_RE.finditer(text)}
    return FIELD_RE.sub("", text).strip(), fields


def render_fields(fields: Dict[str, str]) -> str:
    return "".join(f" [{k}:: {v}]" for k, v in fields.items() if v)


def page_template(ctx: Context, month: str) -> str:
    return (
        "---\n"
        f"context: {ctx.name}\n"
        f"context_slug: {ctx.slug}\n"
        f"month: {month}\n"
        f"type: {PAGE_TYPE}\n"
        "tags: [ptm]\n"
        "---\n\n"
        f"# {ctx.name} — {month_title(month)}\n\n"
        f"{TASKS_HEADING}\n\n"
        f"{LOG_HEADING}\n"
    )


def ensure_page(ctx: Context, month: str, create: bool = True) -> Path:
    path = ctx.page_path(month)
    if not path.exists():
        if not create:
            raise PtmError(f"No page for {ctx.slug} {month} at {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page_template(ctx, month), encoding="utf-8")
    return path


def section_span(lines: List[str], heading: str) -> Tuple[int, int]:
    """Return [start, end) line indices of a section's body, excluding its heading.

    Returns ``(-1, -1)`` when the heading is absent, so callers can add it.
    """
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return -1, -1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i]
        if stripped.startswith("## ") and not stripped.startswith("###"):
            end = i
            break
    return start + 1, end


def read_tasks(ctx: Context, month: str) -> List[Task]:
    path = ctx.page_path(month)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = section_span(lines, TASKS_HEADING)
    if start < 0:
        return []
    tasks: List[Task] = []
    for index in range(start, end):
        match = TASK_RE.match(lines[index])
        if not match:
            continue
        text, fields = strip_fields(match.group("rest"))
        status = STATUS_BY_BOX.get(match.group("box"), "done")
        if status == "open" and fields.get("moved"):
            status = "moved"
        tasks.append(
            Task(
                id=fields.pop("id", ""),
                text=text,
                status=status,
                fields=fields,
                context=ctx.name,
                context_slug=ctx.slug,
                month=month,
                line_no=index,
                raw=lines[index],
            )
        )
    return tasks


def read_notes(ctx: Context, month: str) -> List[Note]:
    path = ctx.page_path(month)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = section_span(lines, LOG_HEADING)
    if start < 0:
        return []

    notes: List[Note] = []
    current_day = ""
    current: Optional[Note] = None
    body_lines: List[str] = []
    in_details = False

    def flush() -> None:
        nonlocal current, body_lines, in_details
        if current:
            current.body = "\n".join(body_lines).strip()
            notes.append(current)
        current, body_lines, in_details = None, [], False

    for index in range(start, end):
        line = lines[index]
        day_match = DAY_RE.match(line)
        if day_match:
            flush()
            current_day = day_match.group("date")
            continue
        entry_match = ENTRY_RE.match(line)
        if entry_match:
            flush()
            current = Note(
                date=current_day,
                time=entry_match.group("time"),
                title=entry_match.group("title").strip(),
                body="",
                details=[],
                tags=[],
                context=ctx.name,
                context_slug=ctx.slug,
                month=month,
            )
            continue
        if not current:
            continue
        if line.strip() == "**Details**":
            in_details = True
            continue
        if in_details and line.strip().startswith("- "):
            current.details.append(line.strip()[2:].strip())
            continue
        if line.startswith("tags:: "):
            current.tags = [t.lstrip("#") for t in line[7:].split()]
            continue
        body_lines.append(line)
    flush()
    return notes


def months_in(ctx: Context) -> List[str]:
    if not ctx.notes_path.is_dir():
        return []
    return sorted(
        p.stem for p in ctx.notes_path.glob("*.md") if MONTH_RE.fullmatch(p.stem)
    )


def months_between(ctx: Context, since: date, until: date) -> List[str]:
    lo, hi = month_of(since), month_of(until)
    return [m for m in months_in(ctx) if lo <= m <= hi]


# --------------------------------------------------------------------------- #
# Goal model
# --------------------------------------------------------------------------- #


@dataclass
class Milestone:
    text: str
    done: bool


@dataclass
class Progress:
    date: str
    text: str


@dataclass
class Goal:
    id: str
    title: str
    status: str
    area: str
    created: str
    year: str
    context: str
    context_slug: str
    path: Path
    description: str
    milestones: List[Milestone]
    progress: List[Progress]

    @property
    def last_progress(self) -> Optional[str]:
        return max((entry.date for entry in self.progress), default=None)

    def as_dict(self, detail: bool = False) -> dict:
        summary = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "area": self.area,
            "created": self.created,
            "year": self.year,
            "context": self.context,
            "context_slug": self.context_slug,
            "path": str(self.path),
            "milestones_done": sum(1 for m in self.milestones if m.done),
            "milestones_total": len(self.milestones),
            "last_progress": self.last_progress,
        }
        if not detail:
            return summary
        return {
            **summary,
            "description": self.description,
            "milestones": [asdict(m) for m in self.milestones],
            "progress": [asdict(p) for p in self.progress],
        }


def frontmatter_span(lines: List[str]) -> Tuple[int, int]:
    """Return [start, end) of the frontmatter's body, or ``(-1, -1)`` if absent."""
    if not lines or lines[0].strip() != "---":
        return -1, -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return 1, index
    return -1, -1


def read_frontmatter(lines: List[str]) -> Dict[str, str]:
    """Frontmatter as strings; unreadable YAML reads as empty, never as an error."""
    start, end = frontmatter_span(lines)
    if start < 0:
        return {}
    try:
        data = yaml.safe_load("\n".join(lines[start:end]))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(key): ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        for key, value in data.items()
        if value is not None
    }


def section_body(lines: List[str], heading: str) -> List[str]:
    start, end = section_span(lines, heading)
    return lines[start:end] if start >= 0 else []


def read_goal(ctx: Context, year: str, path: Path) -> Goal:
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = read_frontmatter(lines)
    milestones = [
        Milestone(text=match.group("rest").strip(), done=match.group("box") in "xX")
        for match in map(TASK_RE.match, section_body(lines, MILESTONES_HEADING))
        if match and match.group("rest").strip()
    ]
    progress = [
        Progress(date=match.group("date"), text=match.group("text").strip())
        for match in map(PROGRESS_RE.match, section_body(lines, PROGRESS_HEADING))
        if match
    ]
    return Goal(
        id=meta.get("id", ""),
        title=path.stem,
        status=meta.get("status") or GOAL_STATUSES[0],
        area=meta.get("area", ""),
        created=meta.get("created", ""),
        year=year,
        context=ctx.name,
        context_slug=ctx.slug,
        path=path,
        description="\n".join(section_body(lines, DESCRIPTION_HEADING)).strip(),
        milestones=milestones,
        progress=progress,
    )


def goal_years(ctx: Context) -> List[str]:
    if not ctx.goals_path.is_dir():
        return []
    return sorted(
        p.name for p in ctx.goals_path.iterdir() if p.is_dir() and YEAR_RE.match(p.name)
    )


def read_goals(ctx: Context, year: str) -> List[Goal]:
    folder = ctx.goal_year_path(year)
    if not folder.is_dir():
        return []
    goals = [read_goal(ctx, year, path) for path in folder.glob("*.md")]
    return sorted(goals, key=lambda goal: goal.title.lower())


def find_goal(
    config: Config, query: str, slug: Optional[str], year_value: Optional[str]
) -> Goal:
    """Resolve a goal by id in any year, else by title within ``year_value``."""
    contexts = config.selection(slug, slug is None)
    for ctx in contexts:
        for year in goal_years(ctx):
            for goal in read_goals(ctx, year):
                if goal.id and goal.id == query:
                    return goal

    year = parse_year(year_value)
    candidates = [goal for ctx in contexts for goal in read_goals(ctx, year)]
    needle = query.strip().lower()
    matches = [g for g in candidates if g.title.lower() == needle] or [
        g for g in candidates if needle in g.title.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise PtmError(f"No goal matching '{query}' in {year}.")
    listing = "\n".join(
        f"  {g.id or '-':<7}  {g.title}  ({g.context} {g.year})" for g in matches
    )
    raise PtmError(
        f"'{query}' matches several goals; use an id or more of the title:\n{listing}"
    )


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def edit_page(path: Path, mutate) -> None:
    """Apply ``mutate(lines) -> lines`` to a page under an exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "r+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            lines = handle.read().splitlines()
            updated = mutate(lines)
            handle.seek(0)
            handle.truncate()
            handle.write("\n".join(updated).rstrip("\n") + "\n")
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def make_id(prefix: str, seed: str, taken: Iterable[str]) -> str:
    seed = f"{seed}/{datetime.now().isoformat()}"
    taken = set(taken)
    for attempt in range(1000):
        digest = hashlib.sha1(f"{seed}/{attempt}".encode()).hexdigest()[:5]
        candidate = f"{prefix}-{digest}"
        if candidate not in taken:
            return candidate
    raise PtmError("Could not allocate a unique id.")


def make_task_id(ctx: Context, month: str, text: str, taken: Iterable[str]) -> str:
    return make_id("t", f"{ctx.slug}/{month}/{text}", taken)


def append_to_section(lines: List[str], heading: str, line: str) -> List[str]:
    """Add ``line`` after a section's last non-blank line, creating the section."""
    start, end = section_span(lines, heading)
    if start < 0:
        return lines + ["", heading, "", line]
    cursor = end
    while cursor > start and not lines[cursor - 1].strip():
        cursor -= 1
    return lines[:cursor] + [line] + lines[cursor:]


def insert_task_line(lines: List[str], line: str) -> List[str]:
    return append_to_section(lines, TASKS_HEADING, line)


def append_goal_line(lines: List[str], heading: str, line: str) -> List[str]:
    """Append to a goal section, keeping the blank line under its heading."""
    start, end = section_span(lines, heading)
    if start >= 0 and not any(text.strip() for text in lines[start:end]):
        return lines[:start] + ["", line] + lines[start:]
    return append_to_section(lines, heading, line)


def insert_note_block(lines: List[str], day: date, block: List[str]) -> List[str]:
    day_heading = f"### {day.isoformat()} ({day.strftime('%a')})"
    start, end = section_span(lines, LOG_HEADING)
    if start < 0:
        return lines + ["", LOG_HEADING, "", day_heading, ""] + block

    day_index = next(
        (
            i
            for i in range(start, end)
            if DAY_RE.match(lines[i])
            and DAY_RE.match(lines[i]).group("date") == day.isoformat()
        ),
        -1,
    )
    if day_index < 0:
        cursor = end
        while cursor > start and not lines[cursor - 1].strip():
            cursor -= 1
        return lines[:cursor] + ["", day_heading, ""] + block + lines[cursor:]

    cursor = end
    for i in range(day_index + 1, end):
        if DAY_RE.match(lines[i]):
            cursor = i
            break
    while cursor > day_index and not lines[cursor - 1].strip():
        cursor -= 1
    return lines[:cursor] + [""] + block + lines[cursor:]


def render_note_block(
    when: datetime, title: str, body: str, details: List[str], tags: List[str]
) -> List[str]:
    block = [f"#### {when.strftime('%H:%M')} — {title}"]
    if tags:
        block.append("tags:: " + " ".join(f"#{t.lstrip('#')}" for t in tags))
    if body.strip():
        block.extend(["", body.rstrip()])
    if details:
        block.extend(["", "**Details**"])
        block.extend(f"- {d}" for d in details)
    return block


def set_frontmatter_value(lines: List[str], key: str, value: str) -> List[str]:
    """Rewrite one ``key:`` line in place, leaving every other property as typed."""
    entry = f"{key}: {value}"
    start, end = frontmatter_span(lines)
    if start < 0:
        return ["---", entry, "---", ""] + lines
    for index in range(start, end):
        if re.match(rf"{re.escape(key)}\s*:", lines[index]):
            lines[index] = entry
            return lines
    return lines[:end] + [entry] + lines[end:]


def yaml_scalar(value: str) -> str:
    # A JSON string is valid YAML, so it safely quotes anything with a colon or #.
    return (
        value if PLAIN_YAML_RE.match(value) else json.dumps(value, ensure_ascii=False)
    )


def goal_title(text: str) -> str:
    title = " ".join(UNSAFE_TITLE_RE.sub("", text).split()).lstrip(".")
    if not title:
        raise PtmError("A goal needs a title Obsidian can use as a file name.")
    return title


def render_goal_note(
    properties: List[Tuple[str, str]],
    title: str,
    description: str = "",
    milestones: Iterable[str] = (),
) -> str:
    lines = ["---", f"type: {GOAL_TYPE}"]
    lines += [f"{key}: {value}".rstrip() for key, value in properties]
    lines += ["tags: [ptm]", "---", "", f"# {title}", "", DESCRIPTION_HEADING, ""]
    if description.strip():
        lines += [description.strip(), ""]
    lines += [MILESTONES_HEADING, ""]
    milestone_lines = [f"- [ ] {text}" for text in milestones]
    if milestone_lines:
        lines += milestone_lines + [""]
    lines += [PROGRESS_HEADING, ""]
    return "\n".join(lines)


GOAL_BASE = """filters:
  and:
    - file.inFolder("{folder}")
properties:
  note.status:
    displayName: Status
  note.area:
    displayName: Area
  file.mtime:
    displayName: Last edited
views:
  - type: table
    name: Goals
    order:
      - file.name
      - note.status
      - note.area
      - file.mtime
  - type: table
    name: By status
    groupBy:
      property: note.status
      direction: ASC
    order:
      - file.name
      - note.area
      - file.mtime
"""


def goal_base(ctx: Context, year: str) -> str:
    return GOAL_BASE.format(folder=f"{ctx.goals_dir}/{year}")


GOAL_NOTE_TEMPLATE = render_goal_note(
    [("status", GOAL_STATUSES[0]), ("area", ""), ("created", "{{date:YYYY-MM-DD}}")],
    "{{title}}",
)


def write_unless_present(path: Path, text: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def read_body(args) -> str:
    if getattr(args, "body_file", None):
        source = args.body_file
        return (
            sys.stdin.read()
            if source == "-"
            else Path(source).read_text(encoding="utf-8")
        )
    body = getattr(args, "body", None) or ""
    return sys.stdin.read() if body == "-" else body


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #


def emit(payload, as_json: bool, render) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        render(payload)


def task_line(task: Task, show_context: bool) -> str:
    mark = {"open": "[ ]", "done": "[x]", "moved": "[>]"}[task.status]
    bits = [task.id.ljust(7), mark, task.text]
    extras = []
    if task.fields.get("due"):
        extras.append(f"due {task.fields['due']}")
    if task.fields.get("prio"):
        extras.append(task.fields["prio"])
    if show_context:
        extras.append(task.context)
    if extras:
        bits.append("(" + ", ".join(extras) + ")")
    return "  " + " ".join(bits)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

DASHBOARD = """---
type: ptm-dashboard
tags: [ptm]
---

# {name}

Open this vault in Obsidian and install the **Dataview** plugin. The yearly
goal tables in `{goals}/YYYY.base` need no plugin — Bases is built in.

## Open tasks, this month

```dataview
TASK FROM "{notes}"
WHERE !completed AND !moved
SORT due ASC
```

## Open tasks with a due date

```dataview
TASK FROM "{notes}"
WHERE !completed AND !moved AND due
SORT due ASC
```

## Everything done this month

```dataview
TASK FROM "{notes}"
WHERE completed
SORT done DESC
```

## Month pages

```dataview
TABLE month AS Month, file.mtime AS Updated
FROM "{notes}"
WHERE type = "ptm-month"
SORT month DESC
```

## Goals this year

```dataview
TABLE WITHOUT ID file.link AS Goal, status AS Status, area AS Area,
  length(filter(file.tasks, (t) => t.completed)) + "/" + length(file.tasks) AS Milestones
FROM "{goals}"
WHERE file.folder = "{goals}/" + dateformat(date(today), "yyyy")
SORT status ASC
```
"""


def cmd_init(args, config: Config) -> int:
    contexts = config.selection(args.context, args.all)
    for ctx in contexts:
        ctx.notes_path.mkdir(parents=True, exist_ok=True)
        page = ensure_page(ctx, parse_month(args.month))
        dashboard = ctx.vault / "_ptm_dashboard.md"
        if not dashboard.exists() or args.force:
            dashboard.write_text(
                DASHBOARD.format(
                    name=ctx.name, notes=ctx.notes_dir, goals=ctx.goals_dir
                ),
                encoding="utf-8",
            )
            note = "written"
        else:
            note = "kept (use --force to restore)"
        print(f"{ctx.slug}: vault {ctx.vault}")
        print(f"  page      {page}")
        print(f"  dashboard {dashboard} — {note}")
    return 0


def cmd_context(args, config: Config) -> int:
    if args.context_command == "add":
        slug = args.slug.lower()
        vault = Path(args.vault).expanduser().resolve()
        config.contexts[slug] = Context(
            slug=slug,
            name=args.name or args.slug,
            vault=vault,
            notes_dir=args.notes_dir,
            goals_dir=args.goals_dir,
        )
        if args.default or not config.default_context:
            config.default_context = slug
        config.save()
        print(f"Added context '{slug}' -> {vault}")
        if config.default_context == slug:
            print(f"Default context is now '{slug}'.")
        print(f"Next: ptmutils init --context {slug}")
        return 0

    if args.context_command == "remove":
        slug = args.slug.lower()
        if slug not in config.contexts:
            raise PtmError(f"Unknown context '{args.slug}'.")
        del config.contexts[slug]
        if config.default_context == slug:
            config.default_context = next(iter(sorted(config.contexts)), None)
        config.save()
        print(f"Removed context '{slug}' from the registry (the vault is untouched).")
        return 0

    if args.context_command == "default":
        ctx = config.resolve(args.slug)
        config.default_context = ctx.slug
        config.save()
        print(f"Default context is now '{ctx.slug}'.")
        return 0

    raise PtmError("Unknown context subcommand.")


def cmd_contexts(args, config: Config) -> int:
    rows = []
    for slug in sorted(config.contexts):
        ctx = config.contexts[slug]
        months = months_in(ctx)
        open_tasks = sum(
            1 for m in months for t in read_tasks(ctx, m) if t.status == "open"
        )
        rows.append(
            {
                **ctx.as_dict(),
                "default": slug == config.default_context,
                "exists": ctx.vault.is_dir(),
                "months": len(months),
                "latest_month": months[-1] if months else None,
                "open_tasks": open_tasks,
            }
        )

    def render(data):
        if not data:
            print("No contexts registered. Add one with `ptmutils context add`.")
            return
        print(f"{'CONTEXT':<14}{'NAME':<24}{'MONTHS':>7}{'OPEN':>6}  VAULT")
        for row in data:
            marker = "*" if row["default"] else " "
            flag = "" if row["exists"] else "  (missing)"
            print(
                f"{marker}{row['slug']:<13}{row['name']:<24}"
                f"{row['months']:>7}{row['open_tasks']:>6}  {row['vault']}{flag}"
            )
        print("\n* = default context")

    emit(rows, args.json, render)
    return 0


def cmd_vault(args, config: Config) -> int:
    rows = []
    for ctx in config.selection(args.context, args.all):
        months = months_in(ctx)
        tasks = [t for m in months for t in read_tasks(ctx, m)]
        rows.append(
            {
                **ctx.as_dict(),
                "exists": ctx.vault.is_dir(),
                "notes_path": str(ctx.notes_path),
                "goals_path": str(ctx.goals_path),
                "goal_years": goal_years(ctx),
                "months": months,
                "notes": sum(len(read_notes(ctx, m)) for m in months),
                "tasks_total": len(tasks),
                "tasks_open": sum(1 for t in tasks if t.status == "open"),
                "config_file": str(config.path),
            }
        )

    def render(data):
        for row in data:
            print(f"Context:  {row['slug']} ({row['name']})")
            print(
                f"Vault:    {row['vault']}{'' if row['exists'] else '  (does not exist yet)'}"
            )
            print(f"Notes:    {row['notes_path']}")
            print(
                f"Goals:    {row['goals_path']}"
                + (f"  ({', '.join(row['goal_years'])})" if row["goal_years"] else "")
            )
            print(
                f"Months:   {len(row['months'])}"
                + (
                    f"  ({row['months'][0]} → {row['months'][-1]})"
                    if row["months"]
                    else ""
                )
            )
            print(
                f"Entries:  {row['notes']} notes, {row['tasks_total']} tasks ({row['tasks_open']} open)"
            )
            print(f"Config:   {row['config_file']}\n")

    emit(rows, args.json, render)
    return 0


def cmd_page(args, config: Config) -> int:
    ctx = config.resolve(args.context)
    month = parse_month(args.month)
    path = ensure_page(ctx, month) if args.create else ctx.page_path(month)
    if args.path:
        print(path)
        return 0
    if not path.exists():
        raise PtmError(f"No page at {path}. Create it with `ptmutils page --create`.")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def cmd_note(args, config: Config) -> int:
    ctx = config.resolve(args.context)
    when_date = parse_date(args.date)
    month = parse_month(args.month, anchor=when_date)
    when_time = (
        datetime.strptime(args.time, "%H:%M").time()
        if args.time
        else datetime.now().time()
    )
    when = datetime.combine(when_date, when_time)

    block = render_note_block(
        when, args.title, read_body(args), args.detail or [], args.tag or []
    )
    payload = {
        "context": ctx.name,
        "context_slug": ctx.slug,
        "month": month,
        "date": when_date.isoformat(),
        "time": when.strftime("%H:%M"),
        "title": args.title,
        "page": str(ctx.page_path(month)),
        "markdown": "\n".join(block),
    }

    if args.dry_run:
        emit(payload, args.json, lambda p: print(p["markdown"]))
        return 0

    path = ensure_page(ctx, month)
    edit_page(path, lambda lines: insert_note_block(lines, when_date, block))
    emit(
        payload,
        args.json,
        lambda p: print(
            f"Noted in {p['context']} {p['month']}: {p['title']}\n  {p['page']}"
        ),
    )
    return 0


def cmd_task(args, config: Config) -> int:
    ctx = config.resolve(args.context)
    month = parse_month(args.month)
    text = " ".join(args.text).strip()
    if not text:
        raise PtmError("A task needs some text.")

    existing = {t.id for m in months_in(ctx) for t in read_tasks(ctx, m)}
    task_id = make_task_id(ctx, month, text, existing)
    fields = {"id": task_id, "added": date.today().isoformat()}
    if args.due:
        fields["due"] = parse_date(args.due).isoformat()
    if args.prio:
        fields["prio"] = args.prio
    tags = " ".join(f"#{t.lstrip('#')}" for t in (args.tag or []))
    line = f"- [ ] {text}{(' ' + tags) if tags else ''}{render_fields(fields)}"

    payload = {
        "id": task_id,
        "text": text,
        "status": "open",
        "context": ctx.name,
        "context_slug": ctx.slug,
        "month": month,
        "page": str(ctx.page_path(month)),
        "markdown": line,
        **{k: v for k, v in fields.items() if k != "id"},
    }

    if args.dry_run:
        emit(payload, args.json, lambda p: print(p["markdown"]))
        return 0

    path = ensure_page(ctx, month)
    edit_page(path, lambda lines: insert_task_line(lines, line))
    emit(
        payload,
        args.json,
        lambda p: print(f"{p['id']}  {p['text']}  ({p['context']} {p['month']})"),
    )
    return 0


def find_task(
    config: Config, task_id: str, slug: Optional[str]
) -> Tuple[Context, str, Task]:
    for ctx in config.selection(slug, slug is None):
        for month in reversed(months_in(ctx)):
            for task in read_tasks(ctx, month):
                if task.id == task_id:
                    return ctx, month, task
    raise PtmError(f"No task with id '{task_id}'.")


def set_task_box(
    config: Config,
    task_id: str,
    slug: Optional[str],
    box: str,
    stamp: Optional[Tuple[str, str]],
) -> dict:
    ctx, month, task = find_task(config, task_id, slug)

    def mutate(lines: List[str]) -> List[str]:
        line = lines[task.line_no]
        match = TASK_RE.match(line)
        rest = match.group("rest")
        rest = FIELD_RE.sub(
            lambda m: "" if m.group("key") in ("done", "moved") else m.group(0), rest
        )
        rest = re.sub(r"\s{2,}", " ", rest).strip()
        if stamp:
            rest = f"{rest} [{stamp[0]}:: {stamp[1]}]"
        lines[task.line_no] = f"{match.group('indent')}- [{box}] {rest}"
        return lines

    edit_page(ctx.page_path(month), mutate)
    return {
        "id": task.id,
        "text": task.text,
        "context": ctx.name,
        "context_slug": ctx.slug,
        "month": month,
        "status": STATUS_BY_BOX.get(box, "done"),
    }


def cmd_done(args, config: Config) -> int:
    stamp = ("done", parse_date(args.date).isoformat())
    results = [
        set_task_box(config, tid, args.context, BOX_DONE, stamp) for tid in args.ids
    ]
    emit(
        results,
        args.json,
        lambda rows: [print(f"done  {r['id']}  {r['text']}") for r in rows],
    )
    return 0


def cmd_undone(args, config: Config) -> int:
    results = [
        set_task_box(config, tid, args.context, BOX_OPEN, None) for tid in args.ids
    ]
    emit(
        results,
        args.json,
        lambda rows: [print(f"open  {r['id']}  {r['text']}") for r in rows],
    )
    return 0


def collect_tasks(args, config: Config) -> List[Task]:
    contexts = config.selection(args.context, args.all)
    months_filter = parse_month(args.month) if args.month else None
    tasks: List[Task] = []
    for ctx in contexts:
        for month in months_in(ctx):
            if months_filter and month != months_filter:
                continue
            tasks.extend(read_tasks(ctx, month))

    if args.status:
        tasks = [t for t in tasks if t.status == args.status]
    elif not args.include_moved:
        tasks = [t for t in tasks if t.status != "moved"]
    if args.due_before:
        limit = parse_date(args.due_before).isoformat()
        tasks = [t for t in tasks if t.fields.get("due") and t.fields["due"] <= limit]
    if args.prio:
        tasks = [t for t in tasks if t.fields.get("prio") == args.prio]
    if args.tag:
        needle = f"#{args.tag.lstrip('#')}"
        tasks = [t for t in tasks if needle in t.text]
    if args.grep:
        needle = args.grep.lower()
        tasks = [t for t in tasks if needle in t.text.lower()]

    def sort_key(task: Task):
        return (task.fields.get("due") or "9999-99-99", task.month, task.text.lower())

    return sorted(tasks, key=sort_key)


def cmd_tasks(args, config: Config) -> int:
    if not args.status and not args.include_moved and not args.any_status:
        args.status = "open"
    tasks = collect_tasks(args, config)

    def render(rows):
        if not rows:
            print("No matching tasks.")
            return
        by_context: Dict[str, List[Task]] = {}
        for task in tasks:
            by_context.setdefault(task.context, []).append(task)
        for name, group in by_context.items():
            print(f"[{name}] ({len(group)})")
            for task in group:
                print(task_line(task, show_context=False))
            print()

    emit([t.as_dict() for t in tasks], args.json, render)
    return 0


def cmd_search(args, config: Config) -> int:
    needle = args.query.lower()
    hits = []
    for ctx in config.selection(args.context, args.all):
        months = months_in(ctx)
        if args.months:
            months = months[-args.months :]
        for month in months:
            for task in read_tasks(ctx, month):
                haystack = " ".join([task.text, *task.fields.values()]).lower()
                if needle in haystack:
                    hits.append({"kind": "task", **task.as_dict()})
            for note in read_notes(ctx, month):
                haystack = " ".join(
                    [note.title, note.body, *note.details, *note.tags]
                ).lower()
                if needle in haystack:
                    hits.append({"kind": "note", **note.as_dict()})

    def render(rows):
        if not rows:
            print(f"Nothing matches '{args.query}'.")
            return
        for row in rows:
            if row["kind"] == "task":
                print(
                    f"task  {row['month']}  [{row['context']}]  {row['id']}  {row['text']}"
                )
            else:
                print(
                    f"note  {row['date']} {row['time']}  [{row['context']}]  {row['title']}"
                )
                if row["body"]:
                    first = row["body"].strip().splitlines()[0]
                    print(f"        {first[:100]}")
        print(f"\n{len(rows)} match(es).")

    emit(hits, args.json, render)
    return 0


def cmd_digest(args, config: Config) -> int:
    today = date.today()
    if args.since or args.until:
        since = (
            parse_date(args.since) if args.since else date(today.year, today.month, 1)
        )
        until = parse_date(args.until) if args.until else today
    elif args.week:
        since = today - timedelta(days=today.weekday())
        until = today
    elif args.last_month:
        since, until = month_bounds(shift_month(month_of(today), -1))
    else:
        month = parse_month(args.month)
        since, until = month_bounds(month)
        if month == month_of(today):
            until = today

    report = []
    for ctx in config.selection(args.context, args.all):
        tasks, notes = [], []
        for month in months_between(ctx, since, until):
            for task in read_tasks(ctx, month):
                stamp = task.fields.get("done") or task.fields.get("added")
                if stamp and not (since.isoformat() <= stamp <= until.isoformat()):
                    continue
                tasks.append(task)
            notes.extend(
                n
                for n in read_notes(ctx, month)
                if since.isoformat() <= n.date <= until.isoformat()
            )
        report.append(
            {
                "context": ctx.name,
                "context_slug": ctx.slug,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "tasks": [t.as_dict() for t in tasks],
                "notes": [n.as_dict() for n in notes],
                "counts": {
                    "open": sum(1 for t in tasks if t.status == "open"),
                    "done": sum(1 for t in tasks if t.status == "done"),
                    "moved": sum(1 for t in tasks if t.status == "moved"),
                    "notes": len(notes),
                },
            }
        )

    def render(rows):
        print(f"Digest — {since.isoformat()} → {until.isoformat()}\n")
        for row in rows:
            counts = row["counts"]
            print(
                f"[{row['context']}]  done {counts['done']} · open {counts['open']} · "
                f"moved {counts['moved']} · notes {counts['notes']}"
            )
            for task in row["tasks"]:
                if task["status"] == "done":
                    print(f"  done  {task.get('done', ''):<15} {task['text']}")
            for task in row["tasks"]:
                if task["status"] == "open":
                    due = f"due {task['due']}" if task.get("due") else ""
                    print(f"  open  {due:<15} {task['text']}")
            for note in row["notes"]:
                print(f"  note  {note['date']}    {note['title']}")
            print()

    emit(report, args.json, render)
    return 0


def cmd_rollover(args, config: Config) -> int:
    source = parse_month(args.source)
    target = args.target and parse_month(args.target) or shift_month(source, 1)
    if target <= source:
        raise PtmError(f"Target month {target} is not after {source}.")

    report = []
    for ctx in config.selection(args.context, args.all):
        open_tasks = [t for t in read_tasks(ctx, source) if t.status == "open"]
        moved = [
            {
                "id": t.id,
                "text": t.text,
                "due": t.fields.get("due"),
                "prio": t.fields.get("prio"),
            }
            for t in open_tasks
        ]
        report.append(
            {
                "context": ctx.name,
                "context_slug": ctx.slug,
                "from": source,
                "to": target,
                "page": str(ctx.page_path(target)),
                "carried": moved,
            }
        )
        if args.dry_run:
            continue

        target_path = ensure_page(ctx, target)
        for task in open_tasks:
            fields = dict(task.fields)
            fields.pop("moved", None)
            line = f"- [ ] {task.text}" + render_fields(
                {"id": task.id, "from": source, **fields}
            )
            edit_page(
                target_path, lambda lines, line=line: insert_task_line(lines, line)
            )

        if open_tasks:
            source_path = ctx.page_path(source)
            line_numbers = {t.line_no for t in open_tasks}

            def mutate(lines: List[str]) -> List[str]:
                for index in line_numbers:
                    match = TASK_RE.match(lines[index])
                    if not match:
                        continue
                    lines[index] = (
                        f"{match.group('indent')}- [{BOX_MOVED}] "
                        f"{match.group('rest')} [moved:: {target}]"
                    )
                return lines

            edit_page(source_path, mutate)

    def render(rows):
        for row in rows:
            verb = "would carry" if args.dry_run else "carried"
            print(
                f"[{row['context']}] {verb} {len(row['carried'])} task(s) {row['from']} → {row['to']}"
            )
            for task in row["carried"]:
                print(f"  {task['id']}  {task['text']}")
            print(f"  page: {row['page']}\n")

    emit(report, args.json, render)
    return 0


def cmd_goal_init(args, config: Config) -> int:
    year = parse_year(args.year)
    report = []
    for ctx in config.selection(args.context, args.all):
        files = {
            "base": (ctx.goal_base_path(year), goal_base(ctx, year)),
            "template": (ctx.goals_path / GOAL_TEMPLATE, GOAL_NOTE_TEMPLATE),
        }
        row = {
            "context": ctx.name,
            "context_slug": ctx.slug,
            "year": year,
            "folder": str(ctx.goal_year_path(year)),
        }
        for name, (path, text) in files.items():
            if args.dry_run:
                written = args.force or not path.exists()
            else:
                written = write_unless_present(path, text, args.force)
            row[name] = {"path": str(path), "written": written}
        if not args.dry_run:
            ctx.goal_year_path(year).mkdir(parents=True, exist_ok=True)
        report.append(row)

    def render(rows):
        for row in rows:
            print(f"{row['context_slug']}: goals {row['year']}")
            print(f"  folder    {row['folder']}")
            for name in ("base", "template"):
                verb = "would write" if args.dry_run else "written"
                state = (
                    verb if row[name]["written"] else "kept (use --force to restore)"
                )
                print(f"  {name:<9} {row[name]['path']} — {state}")

    emit(report, args.json, render)
    return 0


def cmd_goal_add(args, config: Config) -> int:
    ctx = config.resolve(args.context)
    year = parse_year(args.year)
    title = goal_title(" ".join(args.title))
    path = ctx.goal_year_path(year) / f"{title}.md"
    if path.exists():
        raise PtmError(f"A goal named '{title}' already exists in {year}: {path}")

    taken = {g.id for y in goal_years(ctx) for g in read_goals(ctx, y)}
    goal_id = make_id("g", f"{ctx.slug}/{year}/{title}", taken)
    created = parse_date(args.date).isoformat()
    area = (args.area or "").strip()
    description = sys.stdin.read() if args.description == "-" else args.description
    markdown = render_goal_note(
        [
            ("id", goal_id),
            ("status", args.status),
            ("area", yaml_scalar(area) if area else ""),
            ("created", created),
        ],
        title,
        description or "",
        args.milestone or [],
    )
    payload = {
        "id": goal_id,
        "title": title,
        "status": args.status,
        "area": area,
        "created": created,
        "year": year,
        "context": ctx.name,
        "context_slug": ctx.slug,
        "path": str(path),
        "markdown": markdown,
    }

    if args.dry_run:
        emit(payload, args.json, lambda p: print(p["markdown"], end=""))
        return 0

    write_unless_present(ctx.goal_base_path(year), goal_base(ctx, year), force=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(markdown)
    except FileExistsError as exc:
        raise PtmError(f"A goal named '{title}' already exists in {year}.") from exc
    emit(
        payload,
        args.json,
        lambda p: print(
            f"{p['id']}  {p['title']}  ({p['context']} {p['year']})\n  {p['path']}"
        ),
    )
    return 0


def cmd_goal_show(args, config: Config) -> int:
    goal = find_goal(config, args.goal, args.context, args.year)
    emit(
        goal.as_dict(detail=True),
        args.json,
        lambda _: print(goal.path.read_text(encoding="utf-8"), end=""),
    )
    return 0


def report_goal_change(args, goal: Goal, payload: dict, mutate, summary: str) -> int:
    """Shared tail of the goal write commands: dry-run, write, report."""
    payload = {**goal.as_dict(), **payload}
    if args.dry_run:
        emit(payload, args.json, lambda p: print(p.get("markdown", summary)))
        return 0
    edit_page(goal.path, mutate)
    emit(payload, args.json, lambda p: print(summary))
    return 0


def cmd_goal_log(args, config: Config) -> int:
    goal = find_goal(config, args.goal, args.context, args.year)
    text = " ".join(" ".join(args.text).split())
    if not text:
        raise PtmError("A progress entry needs some text.")
    day = parse_date(args.date).isoformat()
    line = f"- {day} — {text}"
    starts_goal = goal.status == "not-started"
    status = "in-progress" if starts_goal else goal.status

    def mutate(lines: List[str]) -> List[str]:
        lines = append_goal_line(lines, PROGRESS_HEADING, line)
        return set_frontmatter_value(lines, "status", status) if starts_goal else lines

    summary = f"{goal.id or '-'}  {goal.title}: {day} — {text}"
    if starts_goal:
        summary += "\n  status: not-started → in-progress"
    payload = {"status": status, "date": day, "text": text, "markdown": line}
    return report_goal_change(args, goal, payload, mutate, summary)


def cmd_goal_status(args, config: Config) -> int:
    goal = find_goal(config, args.goal, args.context, args.year)
    summary = f"{goal.id or '-'}  {goal.title}: {goal.status} → {args.status}"
    return report_goal_change(
        args,
        goal,
        {"status": args.status, "previous_status": goal.status},
        lambda lines: set_frontmatter_value(lines, "status", args.status),
        summary,
    )


def cmd_goal_milestone(args, config: Config) -> int:
    goal = find_goal(config, args.goal, args.context, args.year)
    text = " ".join(" ".join(args.text).split())
    if not text:
        raise PtmError("A milestone needs some text.")
    line = f"- [ ] {text}"
    return report_goal_change(
        args,
        goal,
        {"milestone": text, "markdown": line},
        lambda lines: append_goal_line(lines, MILESTONES_HEADING, line),
        f"{goal.id or '-'}  {goal.title}: + {text}",
    )


def find_milestone(goal: Goal, query: str) -> Milestone:
    needle = query.strip().lower()
    matches = [m for m in goal.milestones if m.text.lower() == needle] or [
        m for m in goal.milestones if needle in m.text.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise PtmError(f"No milestone matching '{query}' in '{goal.title}'.")
    listing = "\n".join(f"  {m.text}" for m in matches)
    raise PtmError(f"'{query}' matches several milestones:\n{listing}")


def set_milestone(args, config: Config, done: bool) -> int:
    goal = find_goal(config, args.goal, args.context, args.year)
    milestone = find_milestone(goal, " ".join(args.milestone))
    box = BOX_DONE if done else BOX_OPEN

    def mutate(lines: List[str]) -> List[str]:
        start, end = section_span(lines, MILESTONES_HEADING)
        for index in range(max(start, 0), max(end, 0)):
            match = TASK_RE.match(lines[index])
            if match and match.group("rest").strip() == milestone.text:
                lines[index] = f"{match.group('indent')}- [{box}] {match.group('rest')}"
                return lines
        raise PtmError(f"Milestone '{milestone.text}' changed on disk; try again.")

    mark = "[x]" if done else "[ ]"
    return report_goal_change(
        args,
        goal,
        {"milestone": milestone.text, "done": done},
        mutate,
        f"{goal.id or '-'}  {goal.title}: {mark} {milestone.text}",
    )


def cmd_goal_check(args, config: Config) -> int:
    return set_milestone(args, config, done=True)


def cmd_goal_uncheck(args, config: Config) -> int:
    return set_milestone(args, config, done=False)


def cmd_goals(args, config: Config) -> int:
    year = parse_year(args.year)
    goals = [
        g
        for ctx in config.selection(args.context, args.all)
        for g in read_goals(ctx, year)
    ]
    if args.status:
        goals = [g for g in goals if g.status == args.status]
    if args.area:
        goals = [g for g in goals if g.area.lower() == args.area.lower()]

    def render(_):
        if not goals:
            print(f"No goals for {year}.")
            return
        by_context: Dict[str, List[Goal]] = {}
        for goal in goals:
            by_context.setdefault(goal.context, []).append(goal)
        for name, group in by_context.items():
            print(f"[{name}] {year} ({len(group)})")
            for goal in group:
                extras = [goal.area] if goal.area else []
                if goal.milestones:
                    done = sum(1 for m in goal.milestones if m.done)
                    extras.append(f"{done}/{len(goal.milestones)}")
                if goal.last_progress:
                    extras.append(f"last {goal.last_progress}")
                suffix = f"  ({', '.join(extras)})" if extras else ""
                print(f"  {goal.id or '-':<7} {goal.status:<11} {goal.title}{suffix}")
            print()

    emit([g.as_dict() for g in goals], args.json, render)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def add_context_flags(parser: argparse.ArgumentParser, allow_all: bool = True) -> None:
    parser.add_argument(
        "--context", "-c", help="Context slug (default: the default context)"
    )
    if allow_all:
        parser.add_argument(
            "--all", "-a", action="store_true", help="Every registered context"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ptmutils",
        description="Personal task management in Obsidian — one vault per context, "
        "one Markdown page per month.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "init", help="Create the vault folders, dashboard and this month's page"
    )
    add_context_flags(p)
    p.add_argument("--month", help="Month to create (default: this month)")
    p.add_argument(
        "--force", action="store_true", help="Overwrite an existing dashboard"
    )
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("contexts", help="List registered contexts")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_contexts)

    p = sub.add_parser("context", help="Register or change a context")
    csub = p.add_subparsers(dest="context_command", required=True)
    add = csub.add_parser("add", help="Register a vault as a context")
    add.add_argument("slug")
    add.add_argument("--vault", required=True, help="Path to the Obsidian vault folder")
    add.add_argument("--name", help="Human-readable name (default: the slug)")
    add.add_argument(
        "--notes-dir",
        default=DEFAULT_NOTES_DIR,
        help="Month pages folder inside the vault",
    )
    add.add_argument(
        "--goals-dir",
        default=DEFAULT_GOALS_DIR,
        help="Goals folder inside the vault",
    )
    add.add_argument(
        "--default", action="store_true", help="Make this the default context"
    )
    remove = csub.add_parser("remove", help="Forget a context (the vault is untouched)")
    remove.add_argument("slug")
    default = csub.add_parser("default", help="Set the default context")
    default.add_argument("slug")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("vault", help="Show resolved paths and vault statistics")
    add_context_flags(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_vault)

    p = sub.add_parser("page", help="Print a month page, or its path")
    add_context_flags(p, allow_all=False)
    p.add_argument("--month", help="YYYY-MM, this, last, next, or +/-N")
    p.add_argument("--path", action="store_true", help="Print the path only")
    p.add_argument("--create", action="store_true", help="Create the page if missing")
    p.set_defaults(func=cmd_page)

    p = sub.add_parser("note", help="Append a timestamped note to the month's log")
    add_context_flags(p, allow_all=False)
    p.add_argument("--title", required=True)
    p.add_argument("--body", help="Body Markdown; '-' reads stdin")
    p.add_argument("--body-file", help="Read the body from a file ('-' = stdin)")
    p.add_argument("--detail", action="append", help="A detail bullet; repeatable")
    p.add_argument(
        "--tag", action="append", help="Obsidian tag without '#'; repeatable"
    )
    p.add_argument("--date", help="YYYY-MM-DD, today, yesterday, or -N")
    p.add_argument("--time", help="HH:MM (default: now)")
    p.add_argument("--month", help="Override the target month page")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("task", help="Add a checklist item to the month's Tasks section")
    p.add_argument("text", nargs="+")
    add_context_flags(p, allow_all=False)
    p.add_argument("--due", help="YYYY-MM-DD, today, tomorrow, or +N")
    p.add_argument("--prio", choices=["low", "med", "high"])
    p.add_argument("--tag", action="append")
    p.add_argument("--month", help="Target month (default: this month)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_task)

    p = sub.add_parser("tasks", help="List checklist items")
    add_context_flags(p)
    p.add_argument("--status", choices=["open", "done", "moved"])
    p.add_argument("--any-status", action="store_true", help="Open and done together")
    p.add_argument("--include-moved", action="store_true")
    p.add_argument("--month")
    p.add_argument("--due-before", help="Only tasks due on or before this date")
    p.add_argument("--prio", choices=["low", "med", "high"])
    p.add_argument("--tag")
    p.add_argument("--grep", help="Substring match on the task text")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("done", help="Check off one or more tasks by id")
    p.add_argument("ids", nargs="+")
    add_context_flags(p, allow_all=False)
    p.add_argument("--date", help="Completion date (default: today)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("undone", help="Re-open one or more tasks by id")
    p.add_argument("ids", nargs="+")
    add_context_flags(p, allow_all=False)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_undone)

    p = sub.add_parser("search", help="Find notes and tasks anywhere in a vault")
    p.add_argument("query")
    add_context_flags(p)
    p.add_argument("--months", type=int, help="Only the last N month pages")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("digest", help="Summarise a period, grouped by context")
    add_context_flags(p)
    p.add_argument("--month", help="YYYY-MM, this, last (default: this month)")
    p.add_argument("--last-month", action="store_true")
    p.add_argument("--week", action="store_true", help="This Monday → today")
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("rollover", help="Carry open tasks into the next month's page")
    add_context_flags(p)
    p.add_argument("--source", help="Month to carry from (default: this month)")
    p.add_argument(
        "--target", help="Month to carry into (default: the month after source)"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rollover)

    year_help = "YYYY, this, last, next, or +/-N (default: this year)"

    p = sub.add_parser(
        "goal", help="Yearly goals: one note per goal, a folder per year"
    )
    gsub = p.add_subparsers(dest="goal_command", required=True)

    def goal_parser(name: str, help_text: str, func) -> argparse.ArgumentParser:
        parser = gsub.add_parser(name, help=help_text)
        parser.set_defaults(func=func)
        return parser

    def add_goal_target(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("goal", help="Goal id, or its title or part of it")
        add_context_flags(parser, allow_all=False)
        parser.add_argument("--year", help=f"Year to match titles in; {year_help}")

    g = goal_parser(
        "init", "Create a year's goals folder, table view and template", cmd_goal_init
    )
    add_context_flags(g)
    g.add_argument("--year", help=year_help)
    g.add_argument(
        "--force", action="store_true", help="Overwrite the view and the template"
    )
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--json", action="store_true")

    g = goal_parser("add", "Create a goal note", cmd_goal_add)
    g.add_argument("title", nargs="+")
    add_context_flags(g, allow_all=False)
    g.add_argument("--area", help="One label, e.g. family or mika")
    g.add_argument("--description", help="Description Markdown; '-' reads stdin")
    g.add_argument("--milestone", action="append", help="A milestone; repeatable")
    g.add_argument("--status", choices=GOAL_STATUSES, default=GOAL_STATUSES[0])
    g.add_argument("--year", help=year_help)
    g.add_argument("--date", help="Created date (default: today)")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--json", action="store_true")

    g = goal_parser("show", "Print a goal note", cmd_goal_show)
    add_goal_target(g)
    g.add_argument("--json", action="store_true")

    g = goal_parser("log", "Append a dated progress entry", cmd_goal_log)
    add_goal_target(g)
    g.add_argument("text", nargs="+")
    g.add_argument("--date", help="YYYY-MM-DD, today, yesterday, or -N")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--json", action="store_true")

    g = goal_parser("status", "Set a goal's status", cmd_goal_status)
    add_goal_target(g)
    g.add_argument("status", choices=GOAL_STATUSES)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--json", action="store_true")

    g = goal_parser("milestone", "Add a milestone to a goal", cmd_goal_milestone)
    add_goal_target(g)
    g.add_argument("text", nargs="+")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--json", action="store_true")

    for name, func, verb in (
        ("check", cmd_goal_check, "Tick"),
        ("uncheck", cmd_goal_uncheck, "Untick"),
    ):
        g = goal_parser(name, f"{verb} a milestone, matched by its text", func)
        add_goal_target(g)
        g.add_argument("milestone", nargs="+", help="The milestone text, or part of it")
        g.add_argument("--dry-run", action="store_true")
        g.add_argument("--json", action="store_true")

    p = sub.add_parser("goals", help="List a year's goals")
    add_context_flags(p)
    p.add_argument("--year", help=year_help)
    p.add_argument("--status", choices=GOAL_STATUSES)
    p.add_argument("--area")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_goals)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args, load_config())
    except PtmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""Unit and end-to-end tests for ptmutils.

The end-to-end tests drive `main()` against throwaway vaults, so they exercise
the real argument parsing, the real file writes, and the page-format contract.
"""

import json
from datetime import date

import pytest

from ptm import ptmutils


def page_text(root, context="nf", month=None):
    """Read a context's month page straight off disk, bypassing the CLI."""
    month = month or ptmutils.month_of(date.today())
    return (root / context / "notes" / f"{month}.md").read_text()


@pytest.fixture
def vaults(tmp_path, monkeypatch, capsys):
    """Two registered contexts pointing at empty throwaway vaults."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("PTM_CONTEXTS_FILE", raising=False)
    monkeypatch.delenv("PTM_DEFAULT_CONTEXT", raising=False)
    monkeypatch.setattr(
        ptmutils, "DEFAULT_CONFIG_DIR", tmp_path / "config" / "ptm", raising=False
    )
    monkeypatch.setattr(ptmutils, "_find_env_file", lambda: None)

    def run(*argv):
        code = ptmutils.main(list(argv))
        assert code == 0, f"ptmutils {' '.join(argv)} exited {code}"
        return capsys.readouterr().out

    run("context", "add", "nf", "--vault", str(tmp_path / "nf"), "--name", "Work")
    run("context", "add", "priv", "--vault", str(tmp_path / "priv"), "--name", "Priv")
    run("init", "--all")
    return run


# --------------------------------------------------------------------------- #
# Month and date arithmetic
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "month,delta,expected",
    [
        ("2026-08", 1, "2026-09"),
        ("2026-12", 1, "2027-01"),
        ("2026-01", -1, "2025-12"),
        ("2026-08", 12, "2027-08"),
    ],
)
def test_shift_month_crosses_year_boundaries(month, delta, expected):
    assert ptmutils.shift_month(month, delta) == expected


def test_parse_month_rejects_an_impossible_month():
    with pytest.raises(ptmutils.PtmError):
        ptmutils.parse_month("2026-99")


def test_parse_month_shorthands():
    anchor = date(2026, 8, 24)
    current = ptmutils.month_of(anchor)
    assert ptmutils.parse_month("2026-03") == "2026-03"
    assert ptmutils.parse_month(None, anchor) == current
    assert ptmutils.parse_month("last", anchor) == "2026-07"
    assert ptmutils.parse_month("next", anchor) == "2026-09"
    assert ptmutils.parse_month("-2", anchor) == "2026-06"


def test_month_bounds_covers_february_in_a_leap_year():
    assert ptmutils.month_bounds("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


def test_parse_date_rejects_nonsense():
    with pytest.raises(ptmutils.PtmError):
        ptmutils.parse_date("next tuesday")


# --------------------------------------------------------------------------- #
# Dataview inline fields
# --------------------------------------------------------------------------- #


def test_strip_fields_separates_prose_from_fields():
    text, fields = ptmutils.strip_fields(
        "Fix login redirect #bug [id:: t-1234a] [due:: 2026-08-30]"
    )
    assert text == "Fix login redirect #bug"
    assert fields == {"id": "t-1234a", "due": "2026-08-30"}


def test_render_fields_drops_empty_values():
    assert ptmutils.render_fields({"id": "t-1", "due": "", "prio": "high"}) == (
        " [id:: t-1] [prio:: high]"
    )


# --------------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------------- #


def test_init_writes_a_page_with_both_sections(vaults, tmp_path):
    page = tmp_path / "nf" / "notes" / f"{ptmutils.month_of(date.today())}.md"
    body = page.read_text()
    assert f"type: {ptmutils.PAGE_TYPE}" in body
    assert ptmutils.TASKS_HEADING in body
    assert ptmutils.LOG_HEADING in body
    assert (tmp_path / "nf" / "_ptm_dashboard.md").exists()


def test_task_then_tasks_round_trips_through_the_page(vaults):
    out = vaults("task", "Fix login redirect", "--due", "2026-12-30", "--prio", "high")
    task_id = out.split()[0]

    listed = json.loads(vaults("tasks", "--json"))
    assert [t["id"] for t in listed] == [task_id]
    assert listed[0]["text"] == "Fix login redirect"
    assert listed[0]["due"] == "2026-12-30"
    assert listed[0]["prio"] == "high"
    assert listed[0]["status"] == "open"


def test_done_marks_the_checkbox_and_stamps_the_date(vaults, tmp_path):
    task_id = vaults("task", "Write the report").split()[0]
    vaults("done", task_id)

    page = page_text(tmp_path)
    assert f"- [x] Write the report [id:: {task_id}]" in page
    assert f"[done:: {date.today().isoformat()}]" in page
    assert json.loads(vaults("tasks", "--json")) == []


def test_undone_reopens_and_clears_the_done_stamp(vaults):
    task_id = vaults("task", "Write the report").split()[0]
    vaults("done", task_id)
    vaults("undone", task_id)

    listed = json.loads(vaults("tasks", "--json"))
    assert listed[0]["status"] == "open"
    assert "done" not in listed[0]


def test_task_ids_are_unique_across_a_context(vaults):
    ids = {vaults("task", f"Task number {n}").split()[0] for n in range(25)}
    assert len(ids) == 25


def test_note_appends_under_a_single_day_heading(vaults, tmp_path):
    vaults("note", "--title", "Sprint planning", "--body", "Deferred the migration.")
    vaults("note", "--title", "Afternoon sync", "--detail", "Backlog groomed")

    page = page_text(tmp_path)
    assert page.count(f"### {date.today().isoformat()}") == 1
    assert "#### " in page
    assert "Deferred the migration." in page
    assert "- Backlog groomed" in page


def test_note_dry_run_writes_nothing(vaults, tmp_path):
    out = vaults("note", "--title", "Not real", "--dry-run")
    page = page_text(tmp_path)
    assert "Not real" in out
    assert "Not real" not in page


def test_search_finds_notes_and_tasks_across_contexts(vaults):
    vaults("task", "Renew passport", "-c", "priv")
    vaults("note", "--title", "Passport appointment booked", "-c", "priv")

    hits = json.loads(vaults("search", "passport", "--all", "--json"))
    assert {h["kind"] for h in hits} == {"task", "note"}


def test_rollover_moves_open_tasks_and_leaves_done_ones_behind(vaults, tmp_path):
    month = ptmutils.month_of(date.today())
    nxt = ptmutils.shift_month(month, 1)
    open_id = vaults("task", "Carry me forward").split()[0]
    done_id = vaults("task", "Already finished").split()[0]
    vaults("done", done_id)

    vaults("rollover", "-c", "nf")

    source = page_text(tmp_path, month=month)
    target = page_text(tmp_path, month=nxt)
    assert f"- [>] Carry me forward [id:: {open_id}]" in source
    assert f"[moved:: {nxt}]" in source
    assert f"- [x] Already finished [id:: {done_id}]" in source
    assert f"[id:: {open_id}]" in target
    assert f"[from:: {month}]" in target
    assert "Already finished" not in target

    still_open = json.loads(vaults("tasks", "--all", "--json"))
    assert [t["id"] for t in still_open] == [open_id]
    assert still_open[0]["month"] == nxt


def test_rollover_dry_run_creates_nothing(vaults, tmp_path):
    vaults("task", "Carry me forward")
    vaults("rollover", "-c", "nf", "--dry-run")
    nxt = ptmutils.shift_month(ptmutils.month_of(date.today()), 1)
    assert not (tmp_path / "nf" / "notes" / f"{nxt}.md").exists()


def test_digest_counts_work_per_context(vaults):
    vaults("task", "Open work")
    done_id = vaults("task", "Closed work").split()[0]
    vaults("done", done_id)
    vaults("note", "--title", "A note")

    digest = json.loads(vaults("digest", "--all", "--json"))
    report = {r["context_slug"]: r for r in digest}
    assert report["nf"]["counts"] == {"open": 1, "done": 1, "moved": 0, "notes": 1}
    assert report["priv"]["counts"]["notes"] == 0


def test_contexts_reports_the_default_and_open_counts(vaults):
    vaults("task", "Something")
    rows = {r["slug"]: r for r in json.loads(vaults("contexts", "--json"))}
    assert rows["nf"]["default"] is True
    assert rows["nf"]["open_tasks"] == 1
    assert rows["priv"]["open_tasks"] == 0


def test_hand_edited_tasks_are_parsed_back(vaults, tmp_path):
    """A task typed straight into Obsidian, with no id, still lists."""
    page = tmp_path / "nf" / "notes" / f"{ptmutils.month_of(date.today())}.md"
    body = page.read_text().replace(
        ptmutils.TASKS_HEADING, f"{ptmutils.TASKS_HEADING}\n- [ ] Typed by hand"
    )
    page.write_text(body)

    listed = json.loads(vaults("tasks", "--json"))
    assert [t["text"] for t in listed] == ["Typed by hand"]
    assert listed[0]["id"] == ""


def test_unknown_context_fails_cleanly(vaults, capsys):
    assert ptmutils.main(["tasks", "-c", "nope"]) == 1
    assert "Unknown context" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Goals
# --------------------------------------------------------------------------- #


def goal_path(root, title, context="nf", year=None):
    year = year or str(date.today().year)
    return root / context / "goals" / year / f"{title}.md"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, date.today().year),
        ("next", date.today().year + 1),
        ("last", date.today().year - 1),
        ("-2", date.today().year - 2),
        ("2030", 2030),
    ],
)
def test_parse_year_shorthands(value, expected):
    assert ptmutils.parse_year(value) == str(expected)


def test_parse_year_rejects_nonsense():
    with pytest.raises(ptmutils.PtmError):
        ptmutils.parse_year("26")


def test_goal_title_drops_characters_obsidian_cannot_name_a_file_with():
    assert (
        ptmutils.goal_title("[Mika] Ops: payroll / stock?") == "Mika Ops payroll stock"
    )
    with pytest.raises(ptmutils.PtmError):
        ptmutils.goal_title("[]")


def test_set_frontmatter_value_keeps_hand_added_properties():
    lines = ["---", "status: done", "mood: great", "---", "# Goal"]
    assert ptmutils.set_frontmatter_value(lines, "status", "in-progress") == [
        "---",
        "status: in-progress",
        "mood: great",
        "---",
        "# Goal",
    ]


def test_goal_add_writes_the_note_and_the_year_view(vaults, tmp_path):
    out = vaults(
        "goal",
        "add",
        "Improve operations",
        "--area",
        "mika",
        "--description",
        "Make operations delegable",
        "--milestone",
        "Payroll",
        "--milestone",
        "Stock",
    )
    goal_id = out.split()[0]
    assert goal_id.startswith("g-")

    note = goal_path(tmp_path, "Improve operations").read_text()
    assert f"type: {ptmutils.GOAL_TYPE}" in note
    assert f"id: {goal_id}" in note
    assert "status: not-started" in note
    assert "area: mika" in note
    assert "Make operations delegable" in note
    assert "- [ ] Payroll\n- [ ] Stock" in note
    assert ptmutils.PROGRESS_HEADING in note

    year = date.today().year
    base = (tmp_path / "nf" / "goals" / f"{year}.base").read_text()
    assert f'file.inFolder("goals/{year}")' in base


def test_goal_add_refuses_to_overwrite_a_goal(vaults, tmp_path, capsys):
    vaults("goal", "add", "Learn to sail")
    assert ptmutils.main(["goal", "add", "Learn to sail"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_goal_add_dry_run_writes_nothing(vaults, tmp_path):
    out = vaults("goal", "add", "Not real", "--dry-run")
    assert "# Not real" in out
    assert not (tmp_path / "nf" / "goals").exists()


def test_goal_add_lands_in_the_requested_year(vaults, tmp_path):
    vaults("goal", "add", "Next year's plan", "--year", "next")
    next_year = str(date.today().year + 1)
    assert goal_path(tmp_path, "Next year's plan", year=next_year).exists()


def test_goal_log_appends_progress_and_starts_the_goal(vaults, tmp_path):
    vaults("goal", "add", "Build robots", "--area", "family")
    vaults("goal", "log", "robots", "Bought", "a", "kit", "--date", "2026-02-03")
    vaults("goal", "log", "robots", "First line follower runs")

    note = goal_path(tmp_path, "Build robots").read_text()
    assert "status: in-progress" in note
    assert "## Progress\n\n- 2026-02-03 — Bought a kit\n- " in note

    shown = json.loads(vaults("goal", "show", "robots", "--json"))
    assert shown["status"] == "in-progress"
    assert [p["text"] for p in shown["progress"]] == [
        "Bought a kit",
        "First line follower runs",
    ]


def test_goal_log_dry_run_writes_nothing(vaults, tmp_path):
    vaults("goal", "add", "Build robots")
    before = goal_path(tmp_path, "Build robots").read_text()
    out = vaults("goal", "log", "robots", "Not real", "--dry-run")
    assert "Not real" in out
    assert goal_path(tmp_path, "Build robots").read_text() == before


def test_goal_status_check_and_milestone(vaults, tmp_path):
    goal_id = vaults(
        "goal", "add", "Improve operations", "--milestone", "Payroll"
    ).split()[0]
    vaults("goal", "milestone", goal_id, "Map invoice ID")
    vaults("goal", "check", goal_id, "invoice")
    vaults("goal", "status", goal_id, "done")

    note = goal_path(tmp_path, "Improve operations").read_text()
    assert "- [ ] Payroll\n- [x] Map invoice ID" in note
    assert "status: done" in note

    vaults("goal", "uncheck", goal_id, "invoice")
    shown = json.loads(vaults("goal", "show", goal_id, "--json"))
    assert shown["milestones_done"] == 0
    assert shown["milestones_total"] == 2


def test_goal_check_refuses_an_ambiguous_milestone(vaults, capsys):
    vaults(
        "goal", "add", "Ops", "--milestone", "Map invoice", "--milestone", "Map stock"
    )
    assert ptmutils.main(["goal", "check", "Ops", "Map"]) == 1
    assert "several milestones" in capsys.readouterr().err


def test_goal_lookup_by_title_is_scoped_to_the_year(vaults, capsys):
    vaults("goal", "add", "Run a marathon", "--year", "last")
    assert ptmutils.main(["goal", "log", "marathon", "Ran 10k"]) == 1
    assert "No goal matching" in capsys.readouterr().err
    vaults("goal", "log", "marathon", "Ran 10k", "--year", "last")


def test_goal_lookup_lists_candidates_when_ambiguous(vaults, capsys):
    vaults("goal", "add", "Plan living abroad")
    vaults("goal", "add", "Plan the wedding")
    assert ptmutils.main(["goal", "show", "plan"]) == 1
    err = capsys.readouterr().err
    assert "Plan living abroad" in err and "Plan the wedding" in err


def test_goals_lists_each_context_with_counts(vaults):
    vaults("goal", "add", "Ship the platform", "--area", "work", "--milestone", "MVP")
    vaults("goal", "add", "Live abroad", "-c", "priv", "--area", "family")
    vaults("goal", "log", "Live abroad", "Visited schools", "--date", "2026-03-14")

    goals = json.loads(vaults("goals", "--all", "--json"))
    by_title = {g["title"]: g for g in goals}
    assert by_title["Ship the platform"]["context_slug"] == "nf"
    assert by_title["Ship the platform"]["milestones_total"] == 1
    assert by_title["Live abroad"]["status"] == "in-progress"
    assert by_title["Live abroad"]["last_progress"] == "2026-03-14"

    family = json.loads(vaults("goals", "--all", "--area", "family", "--json"))
    assert [g["title"] for g in family] == ["Live abroad"]


def test_hand_made_goal_notes_are_read_back(vaults, tmp_path):
    """A note dropped into the year folder by hand, with no frontmatter, lists."""
    path = goal_path(tmp_path, "Read more books")
    path.parent.mkdir(parents=True)
    path.write_text("# Read more books\n\n## Milestones\n- [x] One a month\n")

    goals = json.loads(vaults("goals", "--json"))
    assert goals[0]["title"] == "Read more books"
    assert goals[0]["id"] == ""
    assert goals[0]["status"] == "not-started"
    assert goals[0]["milestones_done"] == 1

    vaults("goal", "log", "books", "Finished Dune")
    note = path.read_text()
    assert note.startswith("---\nstatus: in-progress\n---\n")
    assert "## Progress\n\n- " in note


def test_goal_init_writes_view_and_template_once(vaults, tmp_path):
    vaults("goal", "init", "--all")
    template = tmp_path / "priv" / "goals" / "_templates" / "goal.md"
    assert "{{title}}" in template.read_text()
    template.write_text("customised")

    out = vaults("goal", "init", "-c", "priv")
    assert "kept" in out
    assert template.read_text() == "customised"
    vaults("goal", "init", "-c", "priv", "--force")
    assert "{{title}}" in template.read_text()


def test_goal_init_dry_run_writes_nothing(vaults, tmp_path):
    rows = json.loads(vaults("goal", "init", "--all", "--dry-run", "--json"))
    assert all(row["base"]["written"] for row in rows)
    assert not (tmp_path / "nf" / "goals").exists()


def test_goal_template_is_not_read_as_a_goal(vaults):
    vaults("goal", "init")
    assert json.loads(vaults("goals", "--json")) == []

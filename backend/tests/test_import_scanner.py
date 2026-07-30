"""Directory-import scanner: parsing, security, and API round-trip."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import importer

client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def projects_root(tmp_path, monkeypatch):
    """A scannable root with two project folders and some noise."""
    root = tmp_path / "Projects"
    root.mkdir()

    # ── Project 1: README brief + epic-structured TODO.md ──
    alpha = root / "campus-events_app"
    alpha.mkdir()
    (alpha / "README.md").write_text(
        "# Campus Events\n\n"
        "Students discover campus events, RSVP, and get reminders.\n"
        "Built with ![logo](logo.png) [React](https://react.dev) and `FastAPI`.\n\n"
        "## Goals\n"
        "- Ship MVP in 8 weeks\n"
        "- **Mobile** friendly\n\n"
        "## Constraints\n"
        "- Team of 3\n"
        "- No paid APIs\n",
        encoding="utf-8",
    )
    (alpha / "TODO.md").write_text(
        "# Roadmap\n\n"
        "## Authentication\n"
        "- [x] Set up login (2)\n"
        "- [~] Add password reset [high]\n"
        "- [ ] Social sign-in\n\n"
        "## Event feed\n"
        "- [ ] Render event list (5) [low]\n"
        "- [ ] RSVP button — in progress\n",
        encoding="utf-8",
    )

    # ── Project 2: JSON todos, no README ──
    beta = root / "spentd-api"
    beta.mkdir()
    (beta / "todos.json").write_text(
        json.dumps(
            {
                "todos": [
                    {"title": "Design schema", "status": "done", "points": 5},
                    {"title": "Add auth", "priority": "high"},
                    {"title": "Write docs", "completed": True},
                    "Bare string task",
                ]
            }
        ),
        encoding="utf-8",
    )

    # ── Project 3: plain .todo only ──
    gamma = root / "qit"
    gamma.mkdir()
    (gamma / ".todo").write_text(
        "# notes\n- [ ] Parse args\n- [x] Print version\nBare line task\n",
        encoding="utf-8",
    )

    # ── Noise that must be ignored ──
    (root / "node_modules").mkdir()
    (root / ".hidden").mkdir()
    (root / "loose-file.md").write_text("not a project", encoding="utf-8")

    monkeypatch.setenv("PROJECTS_ROOT", str(root))
    monkeypatch.delenv("PROJECTS_ROOTS", raising=False)
    return root


# ══════════════════════════════════════════════════════════════════════════
# Pure parsing
# ══════════════════════════════════════════════════════════════════════════


def test_humanize_folder_names():
    assert importer.humanize("campus-events_app") == "Campus Events App"
    assert importer.humanize("qit") == "Qit"
    # Deliberate internal capitals are preserved, not flattened.
    assert importer.humanize("GPUcal") == "GPUcal"


def test_markdown_checklist_maps_epics_status_points_priority():
    md = (
        "# Title ignored\n"
        "## Auth\n"
        "- [x] Done thing (2)\n"
        "- [~] Halfway thing [high]\n"
        "- [ ] Fresh thing\n"
        "## Feed\n"
        "- [ ] Feed item (5) [low]\n"
        "- [ ] Marked WIP item\n"
    )
    groups = importer.parse_markdown_checklist(md)
    assert [g["title"] for g in groups] == ["Auth", "Feed"]

    auth = {s["title"]: s for s in groups[0]["stories"]}
    assert auth["Done thing"]["status"] == "done"
    assert auth["Done thing"]["points"] == 2
    assert auth["Halfway thing"]["status"] == "in_progress"
    assert auth["Halfway thing"]["priority"] == "high"
    assert auth["Fresh thing"]["status"] == "todo"
    # Untagged lines take the documented defaults.
    assert auth["Fresh thing"]["points"] == 3
    assert auth["Fresh thing"]["priority"] == "medium"

    feed = {s["title"]: s for s in groups[1]["stories"]}
    assert feed["Feed item"]["points"] == 5
    assert feed["Feed item"]["priority"] == "low"
    # An inline "WIP" word promotes an unchecked item.
    assert feed["Marked item"]["status"] == "in_progress"


def test_checklist_items_before_any_heading_get_default_epic():
    groups = importer.parse_markdown_checklist("- [ ] Loose task\n")
    assert len(groups) == 1
    assert groups[0]["title"] == importer.DEFAULT_EPIC_TITLE


def test_json_todos_shapes():
    from_list = importer.parse_json_todos(json.dumps(["One", "Two"]))
    assert [s["title"] for s in from_list] == ["One", "Two"]

    from_wrapped = importer.parse_json_todos(
        json.dumps({"items": [{"title": "X", "done": True}]})
    )
    assert from_wrapped[0]["status"] == "done"

    # Malformed input degrades to "no stories" rather than raising.
    assert importer.parse_json_todos("{not json") == []
    assert importer.parse_json_todos(json.dumps({"unrelated": 1})) == []


def test_brief_uses_intro_not_whole_readme():
    """The brief is the intro prose, so it doesn't restate Goals/Constraints."""
    md = (
        "# Title\n\n"
        "This is the description of the tool and what it does for people.\n\n"
        "## Goals\n- Ship fast\n\n"
        "## Installation\n- npm install\n"
    )
    lead = importer.md_to_text(importer.lead_section(md))
    assert "description of the tool" in lead
    assert "Ship fast" not in lead
    assert "npm install" not in lead


def test_short_one_line_intro_is_kept_not_treated_as_missing():
    """A brief one-sentence description must not trip the fallback.

    Regression: the fallback threshold was high enough that a legitimate ~38
    character intro was judged "too thin", so the brief swallowed the whole
    README (goals and constraints included).
    """
    md = (
        "# My Cool App\n\n"
        "A **tool** for tracking [things](http://x) with `speed`.\n\n"
        "## Goals\n- Ship v1 fast\n- Keep it small\n\n"
        "## Constraints\n- Solo dev\n"
    )
    brief = importer.md_to_text(importer.lead_section(md))
    assert brief == "A tool for tracking things with speed."
    assert "Ship v1 fast" not in brief
    assert "Solo dev" not in brief


def test_brief_falls_back_when_intro_is_effectively_empty():
    """READMEs that open straight into '## Overview' still get a brief."""
    md = "# Title\n\n## Overview\n\nThe actual description lives down here.\n"
    assert "actual description" in importer.md_to_text(importer.lead_section(md))


def test_md_to_text_strips_markup():
    text = importer.md_to_text(
        "# Heading\n\nSome **bold** and [a link](http://x) plus `code`.\n"
        "```\nignored code block\n```\n"
    )
    assert "**" not in text and "](" not in text
    assert "ignored code block" not in text
    assert "Some bold and a link plus code." in text


# ══════════════════════════════════════════════════════════════════════════
# Folder + root scanning
# ══════════════════════════════════════════════════════════════════════════


def test_scan_happy_path(projects_root):
    result = importer.scan(str(projects_root))

    by_folder = {p["folder"]: p for p in result["projects"]}
    assert set(by_folder) == {"campus-events_app", "spentd-api", "qit"}

    alpha = by_folder["campus-events_app"]
    assert alpha["name"] == "Campus Events App"
    assert "RSVP" in alpha["brief"]
    assert alpha["goals"] == ["Ship MVP in 8 weeks", "Mobile friendly"]
    assert alpha["constraints"] == ["Team of 3", "No paid APIs"]
    assert [e["title"] for e in alpha["epics"]] == ["Authentication", "Event feed"]
    assert alpha["story_count"] == 5
    assert alpha["status_counts"]["done"] == 1
    assert alpha["status_counts"]["in_progress"] == 2

    # No brief file → empty brief, stories still found.
    beta = by_folder["spentd-api"]
    assert beta["brief"] == ""
    assert beta["epics"][0]["title"] == importer.DEFAULT_EPIC_TITLE
    assert beta["story_count"] == 4

    assert by_folder["qit"]["story_count"] == 3

    # node_modules / dotfolders are skipped, loose files are not projects.
    skipped = {s["folder"] for s in result["skipped"]}
    assert "node_modules" in skipped
    assert "loose-file.md" not in {p["folder"] for p in result["projects"]}
    assert result["errors"] == []


def test_scan_ignores_folder_with_no_todo_sources(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "empty-proj").mkdir(parents=True)
    monkeypatch.setenv("PROJECTS_ROOT", str(root))

    result = importer.scan(str(root))
    preview = result["projects"][0]
    assert preview["story_count"] == 0
    assert preview["epics"] == []


# ══════════════════════════════════════════════════════════════════════════
# Security: containment, traversal, symlinks
# ══════════════════════════════════════════════════════════════════════════


def test_path_traversal_is_rejected(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "private").mkdir()
    monkeypatch.setenv("PROJECTS_ROOT", str(allowed))
    monkeypatch.delenv("PROJECTS_ROOTS", raising=False)

    # `..` climbing out of the allowed root
    with pytest.raises(importer.ImportError_, match="outside the allowed"):
        importer.resolve_root(str(allowed / ".." / "secret"))

    # An absolute path elsewhere on disk
    with pytest.raises(importer.ImportError_, match="outside the allowed"):
        importer.resolve_root(str(secret))

    # A path inside the root is fine, `..` or not.
    (allowed / "ok").mkdir()
    assert importer.resolve_root(str(allowed / "ok" / ".." / "ok")) == (
        allowed / "ok"
    ).resolve()


def test_nonexistent_and_file_paths_rejected(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("PROJECTS_ROOT", str(root))

    with pytest.raises(importer.ImportError_, match="does not exist"):
        importer.resolve_root(str(root / "nope"))
    with pytest.raises(importer.ImportError_, match="Not a directory"):
        importer.resolve_root(str(root / "file.txt"))


def test_symlink_escaping_root_is_not_followed(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "TODO.md").write_text("- [ ] Secret task\n", encoding="utf-8")
    (root / "sneaky").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("PROJECTS_ROOT", str(root))

    result = importer.scan(str(root))
    assert result["projects"] == []
    assert any(
        s["reason"] == "symlink outside root" and s["folder"] == "sneaky"
        for s in result["skipped"]
    )


def test_root_defaults_to_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "proj").mkdir(parents=True)
    monkeypatch.setenv("PROJECTS_ROOT", str(root))
    # No explicit path → falls back to the configured root.
    assert importer.resolve_root(None) == root.resolve()
    assert importer.resolve_root("  ") == root.resolve()


# ══════════════════════════════════════════════════════════════════════════
# API: scan → apply → idempotent re-sync
# ══════════════════════════════════════════════════════════════════════════


def test_api_scan_and_apply_roundtrip(projects_root):
    r = client.post("/api/import/scan", json={"root_path": str(projects_root)})
    assert r.status_code == 200
    scan = r.json()
    assert scan["total_projects"] == 3
    assert scan["total_stories"] == 12
    previews = {p["folder"]: p for p in scan["projects"]}
    # Nothing imported yet.
    assert all(p["existing_project_id"] is None for p in previews.values())
    assert previews["campus-events_app"]["new_story_count"] == 5

    # Import a subset.
    r = client.post(
        "/api/import/apply",
        json={
            "root_path": str(projects_root),
            "selections": ["campus-events_app", "qit"],
        },
    )
    assert r.status_code == 200
    applied = r.json()
    assert applied["projects_created"] == 2
    assert applied["projects_resynced"] == 0
    assert applied["stories_created"] == 8
    assert applied["errors"] == []

    alpha_result = next(
        r for r in applied["imported"] if r["folder"] == "campus-events_app"
    )
    assert alpha_result["epics_created"] == 2
    pid = alpha_result["project_id"]

    # Imported data is queryable through the normal endpoints.
    project = client.get(f"/api/projects/{pid}").json()
    assert project["name"] == "Campus Events App"
    assert project["source_path"] == str(projects_root / "campus-events_app")
    assert project["goals"] == ["Ship MVP in 8 weeks", "Mobile friendly"]

    stories = client.get(f"/api/projects/{pid}/stories").json()
    assert len(stories) == 5
    assert {s["status"] for s in stories} == {"todo", "in_progress", "done"}

    # A second scan reports the folder as known with nothing new to add.
    scan2 = client.post(
        "/api/import/scan", json={"root_path": str(projects_root)}
    ).json()
    alpha2 = next(p for p in scan2["projects"] if p["folder"] == "campus-events_app")
    assert alpha2["existing_project_id"] == pid
    assert alpha2["new_story_count"] == 0


def test_api_apply_is_idempotent_and_resyncs_only_new_todos(projects_root):
    folder = projects_root / "campus-events_app"
    body = {"root_path": str(projects_root), "selections": ["campus-events_app"]}

    first = client.post("/api/import/apply", json=body).json()
    pid = first["imported"][0]["project_id"]
    assert first["projects_created"] == 1

    # Re-applying unchanged creates no duplicate project and no new stories.
    second = client.post("/api/import/apply", json=body).json()
    assert second["projects_created"] == 0
    assert second["projects_resynced"] == 1
    assert second["stories_created"] == 0
    assert second["imported"][0]["project_id"] == pid
    assert len(client.get(f"/api/projects/{pid}/stories").json()) == 5

    # A user edit must survive a re-sync.
    stories = client.get(f"/api/projects/{pid}/stories").json()
    edited_id = stories[0]["id"]
    client.patch(
        f"/api/projects/{pid}/stories/{edited_id}",
        json={"points": 13, "status": "done"},
    )

    # New todo appended to an existing epic → only that one is added.
    folder.joinpath("TODO.md").write_text(
        "# Roadmap\n\n"
        "## Authentication\n"
        "- [x] Set up login (2)\n"
        "- [~] Add password reset [high]\n"
        "- [ ] Social sign-in\n"
        "- [ ] Brand new auth task (8)\n\n"
        "## Event feed\n"
        "- [ ] Render event list (5) [low]\n"
        "- [ ] RSVP button — in progress\n",
        encoding="utf-8",
    )

    third = client.post("/api/import/apply", json=body).json()
    assert third["projects_resynced"] == 1
    assert third["stories_created"] == 1
    # Added to the existing epic, not a new one.
    assert third["imported"][0]["epics_created"] == 0

    after = client.get(f"/api/projects/{pid}/stories").json()
    assert len(after) == 6
    assert any(s["title"] == "Brand new auth task" for s in after)
    edited = next(s for s in after if s["id"] == edited_id)
    assert edited["points"] == 13 and edited["status"] == "done"


def test_api_apply_empty_selection_imports_everything(projects_root):
    applied = client.post(
        "/api/import/apply", json={"root_path": str(projects_root)}
    ).json()
    assert applied["projects_created"] == 3
    assert applied["stories_created"] == 12


def test_api_rejects_traversal_with_400(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret"
    secret.mkdir()
    monkeypatch.setenv("PROJECTS_ROOT", str(allowed))
    monkeypatch.delenv("PROJECTS_ROOTS", raising=False)

    for path in (str(allowed / ".." / "secret"), str(secret)):
        r = client.post("/api/import/scan", json={"root_path": path})
        assert r.status_code == 400
        assert "outside the allowed" in r.json()["detail"]

        r = client.post("/api/import/apply", json={"root_path": path})
        assert r.status_code == 400

    # A traversal attempt must not have written anything.
    assert client.post(
        "/api/import/scan", json={"root_path": str(allowed)}
    ).json()["total_projects"] == 0


def test_api_roots_endpoint(projects_root):
    r = client.get("/api/import/roots")
    assert r.status_code == 200
    body = r.json()
    assert body["default_root"] == str(projects_root)
    assert str(projects_root) in body["allowed_roots"]

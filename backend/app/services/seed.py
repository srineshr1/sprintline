"""Seed a realistic demo project when the database is empty."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .. import models


def seed_if_empty(db: Session) -> bool:
    """Create demo project if no projects exist. Returns True if seeded."""
    count = db.query(models.Project).count()
    if count > 0:
        return False

    project = models.Project(
        name="Campus Lost & Found App",
        brief=(
            "A web app for students and staff to report lost items, post found items, "
            "search by category and location, and arrange handoff through campus security. "
            "Mobile-friendly, with email notifications and basic moderation."
        ),
        goals=json.dumps(
            [
                "Students can report lost/found items in under 2 minutes",
                "Security staff can moderate and close claims",
                "Demo-ready MVP for semester showcase",
            ]
        ),
        constraints=json.dumps(
            [
                "Team of 4 part-time students",
                "SQLite for storage",
                "No paid SMS; email only",
            ]
        ),
    )
    db.add(project)
    db.flush()

    epics_data = [
        {
            "title": "Accounts & access",
            "description": "Campus login and basic roles.",
            "order": 0,
            "stories": [
                {
                    "title": "As a student, I want to sign in with campus email so that only community members post items",
                    "description": "Simple email/password auth for demo (no full SSO).",
                    "acceptance_criteria": [
                        "User can register with campus email domain",
                        "Invalid credentials show a clear error",
                        "Session persists across refresh",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "done",
                    "rationale": "Auth is a dependency for posting and claims.",
                    "order": 0,
                },
                {
                    "title": "As security staff, I want a moderator role so that I can review flagged posts",
                    "description": "Role flag on user; gate moderation screens.",
                    "acceptance_criteria": [
                        "Moderator role can open moderation queue",
                        "Regular student cannot access moderation routes",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "done",
                    "rationale": "Needed before public listing goes live.",
                    "order": 1,
                },
            ],
        },
        {
            "title": "Lost & found listings",
            "description": "Core report, search, and detail views.",
            "order": 1,
            "stories": [
                {
                    "title": "As a student, I want to report a lost item so that others know what to look for",
                    "description": "Form: title, category, last seen location, date, photo optional.",
                    "acceptance_criteria": [
                        "Required fields validated before submit",
                        "Item appears in search within 5 seconds",
                        "Reporter can edit their own listing",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "in_progress",
                    "rationale": "Primary student workflow for the product.",
                    "order": 0,
                },
                {
                    "title": "As a student, I want to post a found item so that the owner can claim it",
                    "description": "Similar form with 'found' type and handoff notes.",
                    "acceptance_criteria": [
                        "Found items tagged distinctly from lost",
                        "Contact preference stored (email only)",
                    ],
                    "points": 5,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Symmetric flow to lost reports.",
                    "order": 1,
                },
                {
                    "title": "As a student, I want to filter items by category and building so that I scan less noise",
                    "description": "Filters on list page: category, building, date range.",
                    "acceptance_criteria": [
                        "Filters combine with AND logic",
                        "Empty results show a clear message",
                        "URL reflects filter state for sharing",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Campus has many buildings; search alone is weak.",
                    "order": 2,
                },
                {
                    "title": "As a student, I want item detail with photo and map pin so that I recognize my property",
                    "description": "Detail page with image gallery slot and map placeholder.",
                    "acceptance_criteria": [
                        "Detail shows all form fields",
                        "Missing photo shows placeholder",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Recognition reduces false claims.",
                    "order": 3,
                },
            ],
        },
        {
            "title": "Claims & notifications",
            "description": "Claim workflow and email alerts.",
            "order": 2,
            "stories": [
                {
                    "title": "As a student, I want to file a claim on a found item so that security can verify ownership",
                    "description": "Claim form with proof description; status pending/approved/rejected.",
                    "acceptance_criteria": [
                        "One open claim per user per item",
                        "Owner of listing is notified by email",
                        "Claim status visible on item detail",
                    ],
                    "points": 8,
                    "priority": "high",
                    "status": "todo",
                    "rationale": "Core resolution path; higher effort for notifications.",
                    "order": 0,
                },
                {
                    "title": "As a reporter, I want email when someone claims my listing so that I respond quickly",
                    "description": "Transactional email on claim create.",
                    "acceptance_criteria": [
                        "Email sent in dev via console/log stub",
                        "Email includes item title and claim summary",
                    ],
                    "points": 3,
                    "priority": "medium",
                    "status": "todo",
                    "rationale": "Without alerts, claims go stale.",
                    "order": 1,
                },
                {
                    "title": "As security staff, I want to close a listing after handoff so that the board stays current",
                    "description": "Close action with reason code.",
                    "acceptance_criteria": [
                        "Closed items leave default search",
                        "Close reason stored for audit",
                    ],
                    "points": 2,
                    "priority": "low",
                    "status": "todo",
                    "rationale": "Housekeeping for ops demo.",
                    "order": 2,
                },
            ],
        },
        {
            "title": "Polish & demo",
            "description": "UX and demo reliability.",
            "order": 3,
            "stories": [
                {
                    "title": "As a demo presenter, I want seed sample items so that the board is never empty on stage",
                    "description": "Dev seed of 6 sample listings across categories.",
                    "acceptance_criteria": [
                        "Seed runs once on empty DB",
                        "Sample data is clearly marked",
                    ],
                    "points": 2,
                    "priority": "medium",
                    "status": "in_progress",
                    "rationale": "Demo reliability for viva.",
                    "order": 0,
                },
                {
                    "title": "As a student, I want the list to work on a phone browser so that I can report from campus",
                    "description": "Responsive list and forms at 375px width.",
                    "acceptance_criteria": [
                        "Primary actions reachable without horizontal scroll",
                        "Forms usable on small screens",
                    ],
                    "points": 3,
                    "priority": "low",
                    "status": "todo",
                    "rationale": "Students report on the go.",
                    "order": 1,
                },
            ],
        },
    ]

    all_stories: list[models.Story] = []
    for ep in epics_data:
        epic = models.Epic(
            project_id=project.id,
            title=ep["title"],
            description=ep["description"],
            order=ep["order"],
        )
        db.add(epic)
        db.flush()
        for st in ep["stories"]:
            story = models.Story(
                epic_id=epic.id,
                title=st["title"],
                description=st["description"],
                acceptance_criteria=json.dumps(st["acceptance_criteria"]),
                points=st["points"],
                priority=st["priority"],
                status=st["status"],
                rationale=st["rationale"],
                order=st["order"],
            )
            db.add(story)
            db.flush()
            all_stories.append(story)

    sprint = models.Sprint(
        project_id=project.id,
        name="Sprint 1 — Core listings",
        goal="Auth done; ship lost-item report + list filters for mid-demo",
        capacity_points=20,
        status="active",
        start="2026-08-01",
        end="2026-08-14",
    )
    db.add(sprint)
    db.flush()

    # Assign first ~capacity of incomplete-priority work + some done
    planned = []
    pts = 0
    for s in all_stories:
        if s.status == "done" or s.priority == "high" or s.status == "in_progress":
            if pts + s.points <= 22 or s.status in ("done", "in_progress"):
                planned.append(s)
                pts += s.points
        if len(planned) >= 6:
            break

    for s in planned:
        db.add(models.SprintItem(sprint_id=sprint.id, story_id=s.id))

    db.add(
        models.Activity(
            project_id=project.id,
            type="seed_demo",
            payload=json.dumps({"name": project.name, "stories": len(all_stories)}),
        )
    )
    db.commit()
    return True

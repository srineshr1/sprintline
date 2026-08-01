"""Token-budget settings, usage counters, and pack limits."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings, get_settings
from app.services import codebase, llm
from app.services.ai_agents import _compact_json


def test_compact_json_is_minified() -> None:
    raw = _compact_json({"a": 1, "b": ["x", "y"]})
    assert " " not in raw
    assert "\n" not in raw
    assert raw == '{"a":1,"b":["x","y"]}'


def test_default_token_budgets_are_frugal() -> None:
    # Isolate from any process env overrides set outside tests
    keys = [
        "SPRINTLINE_BACKLOG_MAX_FILES",
        "SPRINTLINE_BACKLOG_MAX_CHARS",
        "SPRINTLINE_BACKLOG_MAX_TOKENS",
        "SPRINTLINE_SPRINT_MAX_TOKENS",
        "SPRINTLINE_STANDUP_MAX_TOKENS",
        "SPRINTLINE_IMPORT_MAX_TOKENS",
        "SPRINTLINE_IMPORT_MAX_CHARS",
    ]
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        s = Settings()
        assert s.backlog_max_files == 12
        assert s.backlog_max_chars == 10_000
        assert s.backlog_max_tokens == 2_500
        assert s.sprint_max_tokens == 1_200
        assert s.standup_max_tokens == 900
        assert s.import_max_tokens == 1_400
        assert s.import_max_chars == 4_000
        budgets = s.token_budgets()
        assert budgets["backlog_max_files"] == 12
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_token_budget_env_overrides() -> None:
    os.environ["SPRINTLINE_BACKLOG_MAX_FILES"] = "8"
    os.environ["SPRINTLINE_BACKLOG_MAX_CHARS"] = "6000"
    os.environ["SPRINTLINE_BACKLOG_MAX_TOKENS"] = "1800"
    try:
        s = Settings()
        assert s.backlog_max_files == 8
        assert s.backlog_max_chars == 6000
        assert s.backlog_max_tokens == 1800
    finally:
        for k in (
            "SPRINTLINE_BACKLOG_MAX_FILES",
            "SPRINTLINE_BACKLOG_MAX_CHARS",
            "SPRINTLINE_BACKLOG_MAX_TOKENS",
        ):
            os.environ.pop(k, None)


def test_usage_snapshot_records_tokens() -> None:
    llm.reset_usage()
    resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=40, total_tokens=140)
    )
    llm._record_usage(resp, model="test-model")
    snap = llm.usage_snapshot()
    assert snap["calls"] == 1
    assert snap["prompt_tokens"] == 100
    assert snap["completion_tokens"] == 40
    assert snap["total_tokens"] == 140
    assert snap["by_model"]["test-model"]["prompt_tokens"] == 100
    assert snap["last_call"]["model"] == "test-model"
    llm.reset_usage()
    assert llm.usage_snapshot()["calls"] == 0


def test_collect_project_context_respects_max_files(tmp_path: Path) -> None:
    for i in range(20):
        (tmp_path / f"file_{i:02d}.md").write_text(f"# doc {i}\n" + ("x" * 50), encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project\nImportant overview.", encoding="utf-8")

    ctx = codebase.collect_project_context(
        tmp_path, max_files=5, max_total_chars=50_000
    )
    assert ctx["exists"] is True
    assert len(ctx["files"]) <= 5
    # High-priority README should win ranking
    assert any(f["path"] == "README.md" for f in ctx["files"])


def test_ai_status_includes_budgets_and_usage() -> None:
    get_settings.cache_clear()
    status = get_settings().ai_status()
    assert "token_budgets" in status
    assert "usage" in status
    assert status["token_budgets"]["backlog_max_files"] >= 1
    assert "prompt_tokens" in status["usage"]

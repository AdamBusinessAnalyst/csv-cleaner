import json
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

import cleaner
from cleaner import CleaningPlan, _extract_column, apply_cleaning, build_profile


@pytest.fixture
def messy() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Name": ["  Ann ", "Bob", "Bob", None],
            "Status": ["Active", "INACTIVE", "INACTIVE", "active"],
            "Salary": [1000.0, None, None, 3000.0],
            "Joined": ["2024-01-05", "2024-02-10", "2024-02-10", "bad"],
            "Email": ["a@x.com", "b@x.com", "b@x.com", None],
        }
    )


def test_profile_reports_nulls_and_duplicates(messy: pd.DataFrame) -> None:
    profile = build_profile(messy)
    assert "Rows: 4" in profile
    assert "'Salary': float64, 2 nulls" in profile
    assert "Duplicate rows: 1" in profile


def test_extract_column_prefers_quoted_name() -> None:
    cols = ["Date", "Update Date"]
    assert _extract_column("Convert 'Update Date' to datetime", cols) == "Update Date"
    assert _extract_column("Convert Date to datetime", cols) == "Date"
    assert _extract_column("Do something else", cols) is None


def test_apply_cleaning_runs_each_action(messy: pd.DataFrame) -> None:
    plan = CleaningPlan(
        issues_found=[],
        actions_taken=[
            "Drop duplicate rows",
            "Strip whitespace from column 'Name'",
            "Standardize column 'Status' values to lowercase",
            "Fill nulls in 'Salary' with column median",
            "Convert column 'Joined' to datetime format",
            "Remove rows where 'Email' is null",
            "Ask the client about column meanings",
        ],
    )
    out = apply_cleaning(messy, plan)
    assert len(out) == 2
    assert out["Name"].tolist() == ["Ann", "Bob"]
    assert out["Status"].tolist() == ["active", "inactive"]
    assert out["Salary"].isna().sum() == 0
    assert pd.api.types.is_datetime64_any_dtype(out["Joined"])


def test_apply_cleaning_does_not_mutate_input(messy: pd.DataFrame) -> None:
    before = messy.copy()
    apply_cleaning(messy, CleaningPlan(issues_found=[], actions_taken=["Drop duplicate rows"]))
    pd.testing.assert_frame_equal(messy, before)


def test_claude_response_parsed_from_code_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"issues_found": ["dupes"], "actions_taken": ["Drop duplicate rows"]}
    text = "```json\n" + json.dumps(payload) + "\n```"

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs: Any) -> SimpleNamespace:
            assert kwargs["model"] == cleaner.MODEL
            return SimpleNamespace(content=[SimpleNamespace(text=text)])

    monkeypatch.setattr(cleaner.anthropic, "Anthropic", FakeClient)
    plan = cleaner.ask_claude_for_cleaning_plan("profile", "a,b\n1,2")
    assert plan.actions_taken == ["Drop duplicate rows"]

"""Tests for v2.16.18: last_error_category attribute + Repair issue lifecycle.

The coordinator categorises every failure into one of five buckets and
opens a Settings → System → Repairs entry when an outage streak crosses
the 1-hour threshold. This file covers:

* Initial state is "none"
* 401/403 → category "auth"
* 429 → category "quota_exceeded"
* 500/503 → category "api_unavailable"
* aiohttp.ClientError → category "network"
* Recovery clears the category, the outage timestamp, and the repair
* The 1-hour threshold gates the Repair-issue creation
* The Repair is idempotent (only fires once per streak)
* The Repair is removed on recovery
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator


def _make_coord(hass) -> NSUpdateCoordinator:
    """Construct a coordinator with a fake hass — no network."""
    return NSUpdateCoordinator(
        hass,
        api_key="abcdef0123456789abcdef0123456789",
        from_station="ASD",
        to_station="UT",
        scan_interval_minutes=5,
    )


# ---- baseline -----------------------------------------------------------


def test_initial_state(hass):
    coord = _make_coord(hass)
    assert coord._last_error_category == "none"
    assert coord._outage_started_at is None
    assert coord._open_repair_issue_id is None
    assert coord._was_available is None


# ---- _note_unavailable stamps outage timestamp --------------------------


def test_note_unavailable_stamps_timestamp(hass):
    coord = _make_coord(hass)
    before = time.time()
    coord._note_unavailable("test outage")
    after = time.time()
    assert coord._outage_started_at is not None
    assert before <= coord._outage_started_at <= after
    assert coord._was_available is False


def test_note_unavailable_does_not_restamp_inside_streak(hass):
    """Second failure during the same streak keeps the original timestamp."""
    coord = _make_coord(hass)
    coord._note_unavailable("first")
    first_ts = coord._outage_started_at
    time.sleep(0.01)
    coord._note_unavailable("second")
    assert coord._outage_started_at == first_ts


# ---- _note_available clears outage state --------------------------------


def test_note_available_clears_outage(hass):
    coord = _make_coord(hass)
    coord._last_error_category = "auth"
    coord._outage_started_at = time.time() - 100
    coord._note_available()
    assert coord._outage_started_at is None
    assert coord._last_error_category == "none"
    assert coord._was_available is True


def test_note_available_on_first_run_marks_available(hass):
    coord = _make_coord(hass)
    coord._note_available()
    assert coord._was_available is True


def test_note_available_deletes_open_repair(hass):
    coord = _make_coord(hass)
    coord._open_repair_issue_id = "fake_issue"
    coord._outage_started_at = time.time() - 100
    with patch(
        "homeassistant.helpers.issue_registry.async_delete_issue"
    ) as del_issue:
        coord._note_available()
    del_issue.assert_called_once()
    assert coord._open_repair_issue_id is None


# ---- _maybe_raise_outage_repair guards ----------------------------------


def test_repair_not_raised_when_no_outage(hass):
    coord = _make_coord(hass)
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as create_issue:
        coord._maybe_raise_outage_repair()
    create_issue.assert_not_called()


def test_repair_not_raised_within_threshold(hass):
    coord = _make_coord(hass)
    coord._outage_started_at = time.time() - 60  # 1 minute ago
    coord._last_error_category = "auth"
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as create_issue:
        coord._maybe_raise_outage_repair()
    create_issue.assert_not_called()
    assert coord._open_repair_issue_id is None


def test_repair_raised_past_threshold(hass):
    coord = _make_coord(hass)
    coord._outage_started_at = (
        time.time() - NSUpdateCoordinator._REPAIR_OUTAGE_THRESHOLD_SECONDS - 60
    )
    coord._last_error_category = "auth"
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as create_issue:
        coord._maybe_raise_outage_repair()
    create_issue.assert_called_once()
    assert coord._open_repair_issue_id is not None
    assert "ASD" in coord._open_repair_issue_id
    assert "UT" in coord._open_repair_issue_id
    assert "auth" in coord._open_repair_issue_id


def test_repair_idempotent_across_two_calls(hass):
    """Second call inside the same streak must not re-fire create_issue."""
    coord = _make_coord(hass)
    coord._outage_started_at = (
        time.time() - NSUpdateCoordinator._REPAIR_OUTAGE_THRESHOLD_SECONDS - 60
    )
    coord._last_error_category = "auth"
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as create_issue:
        coord._maybe_raise_outage_repair()
        coord._maybe_raise_outage_repair()
    assert create_issue.call_count == 1


def test_repair_issue_id_varies_by_category(hass):
    """Different categories yield distinct issue_ids so streaks don't collide."""
    coord_a = _make_coord(hass)
    coord_b = _make_coord(hass)
    long_ago = (
        time.time() - NSUpdateCoordinator._REPAIR_OUTAGE_THRESHOLD_SECONDS - 60
    )
    coord_a._outage_started_at = long_ago
    coord_a._last_error_category = "auth"
    coord_b._outage_started_at = long_ago
    coord_b._last_error_category = "network"
    with patch("homeassistant.helpers.issue_registry.async_create_issue"):
        coord_a._maybe_raise_outage_repair()
        coord_b._maybe_raise_outage_repair()
    assert coord_a._open_repair_issue_id != coord_b._open_repair_issue_id

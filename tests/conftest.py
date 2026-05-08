"""Test fixtures for the NS Reisadvies integration."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,  # noqa: ARG001
) -> None:
    """Enable loading of the custom integration in every test."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Skip the actual setup_entry — the config flow only creates the entry."""
    with patch(
        "custom_components.ns_reisadvies.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock

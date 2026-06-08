"""Unit tests for v2.16.14's ``sanitize_api_key`` helper.

The helper exists to defend against copy-paste-induced HTTP 401s: NS
Apportal's account page sometimes silently appends a zero-width space,
BOM, or non-breaking space, and Python's plain ``str.strip()`` ignores
all of those. With them in the key, the ``Ocp-Apim-Subscription-Key``
header is malformed and NS APIM rejects the request as 401 — without
any visible difference in the UI the user pasted from.
"""
from __future__ import annotations

import pytest

from custom_components.ns_reisadvies.coordinator import sanitize_api_key


def test_clean_key_passes_through_unchanged():
    """A normal-looking key is returned exactly as given."""
    key = "abc123def456"
    assert sanitize_api_key(key) == key


def test_idempotent():
    """Sanitising twice yields the same result."""
    key = "  \tabc123  \n"
    once = sanitize_api_key(key)
    twice = sanitize_api_key(once)
    assert once == twice == "abc123"


@pytest.mark.parametrize("value", [None, 0, 1, [], {}, object()])
def test_non_string_returns_empty_string(value):
    """Non-string inputs collapse to ``""``."""
    assert sanitize_api_key(value) == ""


def test_strips_ascii_whitespace_ring():
    assert sanitize_api_key(" key ") == "key"
    assert sanitize_api_key("\tkey\n") == "key"
    assert sanitize_api_key("\r\nkey") == "key"


def test_strips_zero_width_space():
    """ZWSP at either end is removed (regression: HA 2026.6.1 401)."""
    assert sanitize_api_key("​abcdef") == "abcdef"
    assert sanitize_api_key("abcdef​") == "abcdef"
    assert sanitize_api_key("​ abcdef ​") == "abcdef"


def test_strips_bom():
    """UTF-8 BOM (U+FEFF) is removed."""
    assert sanitize_api_key("﻿abcdef") == "abcdef"
    assert sanitize_api_key("abcdef﻿") == "abcdef"


def test_strips_nbsp():
    """Non-breaking space (U+00A0) is removed."""
    assert sanitize_api_key(" abcdef ") == "abcdef"


def test_strips_zero_width_joiner_and_non_joiner():
    """ZWJ + ZWNJ at the edges are removed."""
    assert sanitize_api_key("‌abc‍") == "abc"


def test_strips_line_and_paragraph_separator():
    """Unicode LSEP (U+2028) and PSEP (U+2029) are removed."""
    assert sanitize_api_key(" abc ") == "abc"


def test_strips_mid_string_control_characters():
    """ASCII control chars embedded mid-string are removed.

    Some copy-paste pipelines (e.g. a key spanning two lines in a
    password manager) insert a CR or LF in the middle of the key, which
    plain ``.strip()`` cannot reach. They must not survive into the HTTP
    header value either.
    """
    assert sanitize_api_key("abc\rdef") == "abcdef"
    assert sanitize_api_key("abc\ndef") == "abcdef"
    assert sanitize_api_key("abc\tdef") == "abcdef"
    assert sanitize_api_key("abc\x00def") == "abcdef"


def test_combination_of_invisible_characters():
    """Realistic worst-case: ZWSP at start, NBSP in middle, BOM at end."""
    pasted = "​" + "abcd" + " " + "efgh" + "﻿"
    # NBSP is inside the string, so the leading/trailing strips leave it
    # in place — but our ASCII-control filter only removes ord < 0x20,
    # so the NBSP at U+00A0 still survives mid-string. That's intentional:
    # NS' subscription-key alphabet only uses [A-Za-z0-9], so a key with
    # an internal NBSP was already malformed in the source — better to
    # surface it as 401 than to silently rewrite the user's input. The
    # only thing we guarantee is the leading/trailing ring is clean.
    cleaned = sanitize_api_key(pasted)
    assert not cleaned.startswith("​")
    assert not cleaned.endswith("﻿")
    assert cleaned.startswith("abcd")
    assert cleaned.endswith("efgh")


def test_empty_after_stripping_returns_empty_string():
    """An input consisting solely of whitespace + invisibles becomes ``""``."""
    assert sanitize_api_key("​  \t\n") == ""


def test_long_realistic_key_unchanged():
    """A 32-character hex key (the NS Apportal format) passes through."""
    key = "0123456789abcdef0123456789abcdef"
    assert sanitize_api_key(key) == key

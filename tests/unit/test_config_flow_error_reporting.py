"""Unit tests for how setup failures are reported to the user.

Issue #18: every failure in `validate_connection` raised a bare ConnectionError
and surfaced as "Failed to connect to the printer. Please check the IP address
and credentials." A response the library could not parse, an unreachable
printer, and a genuinely wrong check code were indistinguishable - and the one
message on offer blamed the credentials in all three cases. Two reporters read
that same message two different ways ("check code not working" and
"cannot_connect / TCP problem"); neither had a credential problem.

These tests pin the distinction: only a printer that answered and refused
produces `invalid_auth`.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.ha_mocks import mock_homeassistant

mock_homeassistant()
sys.modules["voluptuous"] = MagicMock()

from custom_components.flashforge.config_flow import (
    InvalidAuthError,
    UnsupportedPrinterError,
    validate_connection,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

ENTRY = {
    CONF_NAME: "Creator 5 Pro",
    CONF_IP_ADDRESS: "192.168.1.120",
    "serial_number": "SN123456",
    "check_code": "12345678",
}


def _client(*, detail=None, machine_info=True, product_ok=True) -> Mock:
    client = Mock()
    client.info.get_detail_response = AsyncMock(
        return_value=SimpleNamespace(detail=detail) if detail is not None else None
    )
    client.info.get = AsyncMock(
        return_value=SimpleNamespace(name="Creator 5 Pro") if machine_info else None
    )
    client.cache_details = Mock()
    client.send_product_command = AsyncMock(return_value=product_ok)
    client._http_session = None
    return client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejected_credentials_raise_invalid_auth():
    """The one case that really is a credential problem."""
    client = _client(detail=SimpleNamespace(pid=41, name="Creator 5 Pro"), product_ok=False)

    with patch("custom_components.flashforge.config_flow.FlashForgeClient", return_value=client):
        with pytest.raises(InvalidAuthError):
            await validate_connection(Mock(), ENTRY)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unreadable_detail_is_not_reported_as_bad_credentials():
    """A /detail the library could not parse comes back as None.

    That is the issue #18 path. It must stay a plain ConnectionError, so the
    user is not told their check code is wrong when it is not.
    """
    client = _client(detail=None)

    with patch("custom_components.flashforge.config_flow.FlashForgeClient", return_value=client):
        with pytest.raises(ConnectionError) as excinfo:
            await validate_connection(Mock(), ENTRY)

    assert not isinstance(excinfo.value, InvalidAuthError)
    client.send_product_command.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unparseable_machine_info_is_not_reported_as_bad_credentials():
    """Same rule for the second /detail read, which parses into FFMachineInfo."""
    client = _client(
        detail=SimpleNamespace(pid=41, name="Creator 5 Pro"), machine_info=False
    )

    with patch("custom_components.flashforge.config_flow.FlashForgeClient", return_value=client):
        with pytest.raises(ConnectionError) as excinfo:
            await validate_connection(Mock(), ENTRY)

    assert not isinstance(excinfo.value, InvalidAuthError)


@pytest.mark.unit
def test_invalid_auth_is_caught_before_connection_error():
    """InvalidAuthError subclasses ConnectionError, so handler order matters.

    If `except ConnectionError` were listed first it would swallow every auth
    failure and the new message would never be shown.
    """
    source = (
        project_root / "custom_components" / "flashforge" / "config_flow.py"
    ).read_text(encoding="utf-8")

    # Four flows handle these: user, manual, reauth, reconfigure.
    assert source.count('errors["base"] = "invalid_auth"') == 4
    for block in source.split("except UnsupportedPrinterError:")[1:]:
        auth_at = block.find("except InvalidAuthError:")
        conn_at = block.find("except ConnectionError:")
        assert auth_at != -1, "every handler chain must catch InvalidAuthError"
        assert auth_at < conn_at, "InvalidAuthError must be caught before ConnectionError"


@pytest.mark.unit
def test_error_strings_exist_and_stop_blaming_the_credentials():
    """The connection message must not assert the credentials are wrong."""
    for name in ("strings.json", "translations/en.json"):
        path = project_root / "custom_components" / "flashforge" / name
        errors = json.loads(path.read_text(encoding="utf-8"))["config"]["error"]

        assert "invalid_auth" in errors, f"{name} is missing invalid_auth"
        assert "cannot_connect" in errors

        # The old wording, which sent both #18 reporters chasing their check code.
        assert "check the IP address and credentials" not in errors["cannot_connect"]
        # Both messages should point at the log, which is now where the real
        # cause is recorded (flashforge-python-api >= 1.3.3).
        assert "log" in errors["cannot_connect"].lower()
        assert "log" in errors["invalid_auth"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unsupported_printer_still_wins_over_auth():
    """An unsupported model is reported as such, not as an auth failure."""
    client = _client(detail=SimpleNamespace(pid=30, name="Adventurer 4"), product_ok=False)

    with patch("custom_components.flashforge.config_flow.FlashForgeClient", return_value=client):
        with pytest.raises(UnsupportedPrinterError):
            await validate_connection(Mock(), ENTRY)

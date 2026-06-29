"""Unit tests for the FlashForge select entity descriptions."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.ha_mocks import mock_homeassistant

mock_homeassistant()

from custom_components.flashforge.select import SELECTS


def _select_by_key(key: str):
    for select in SELECTS:
        if select.key == key:
            return select
    raise ValueError(f"Select with key '{key}' not found")


@pytest.mark.unit
def test_filtration_select_availability_gated_on_model():
    """Filtration availability follows model identity (5M Pro / Creator 5 Pro).

    The printer's /product endpoint is unreliable for capability detection (it
    misreports Creator 5 Pro filtration), so availability is derived from the
    firmware PID / model flags rather than the /product-derived capability flag.
    """
    filtration_select = _select_by_key("filtration_mode")
    fn = filtration_select.availability_fn

    # Regular models (no filtration hardware) -> unavailable
    data = Mock(is_pro=False, is_creator5_pro=False)
    assert fn(data) is False

    # Adventurer 5M Pro -> available
    data = Mock(is_pro=True, is_creator5_pro=False)
    assert fn(data) is True

    # Creator 5 Pro -> available
    data = Mock(is_pro=False, is_creator5_pro=True)
    assert fn(data) is True

    # Regular Creator 5 (heater, but no filtration) -> unavailable
    data = Mock(is_pro=False, is_creator5_pro=False, is_creator5=True)
    assert fn(data) is False


"""Image platform for FlashForge integration — exposes the current g-code thumbnail."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FlashForgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FlashForge thumbnail image from a config entry."""
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    printer_name: str = hass.data[DOMAIN][entry.entry_id]["name"]

    async_add_entities(
        [FlashForgeThumbnailImage(hass, coordinator, printer_name, entry.entry_id)]
    )


class FlashForgeThumbnailImage(
    CoordinatorEntity[FlashForgeDataUpdateCoordinator], ImageEntity
):
    """Image entity exposing the thumbnail of the currently printing g-code file."""

    _attr_has_entity_name = True
    _attr_name = "Current File Thumbnail"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: FlashForgeDataUpdateCoordinator,
        printer_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the thumbnail image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)

        self._attr_unique_id = f"{entry_id}_thumbnail"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": printer_name,
            "manufacturer": "FlashForge",
        }

        self._cached_file: str | None = None
        self._cached_bytes: bytes | None = None

    def _current_file(self) -> str | None:
        """Return the current print file name, or None if idle."""
        if self.coordinator.data is None:
            return None
        name = getattr(self.coordinator.data, "print_file_name", None)
        return name or None

    @property
    def available(self) -> bool:
        """Available when the coordinator is healthy and a file is loaded."""
        return (
            self.coordinator.last_update_success
            and self._current_file() is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose the current file name alongside the image."""
        return {"file_name": self._current_file()}

    async def async_added_to_hass(self) -> None:
        """Initialize timestamp from the first coordinator snapshot."""
        await super().async_added_to_hass()
        current = self._current_file()
        if current is not None and self._attr_image_last_updated is None:
            self._cached_file = current
            self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        """Bump the image timestamp when the active file changes."""
        current = self._current_file()
        if current != self._cached_file:
            self._cached_file = current
            self._cached_bytes = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return the thumbnail image bytes for the current file."""
        current = self._current_file()
        if current is None:
            return None

        if self._cached_bytes is not None and self._cached_file == current:
            return self._cached_bytes

        try:
            data = await self.coordinator.client.files.get_gcode_thumbnail(current)
        except Exception as err:  # noqa: BLE001 - upstream may raise broadly
            _LOGGER.debug("Thumbnail fetch failed for %s: %s", current, err)
            return None

        if data:
            self._cached_file = current
            self._cached_bytes = data
        return data

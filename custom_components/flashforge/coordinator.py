"""DataUpdateCoordinator for FlashForge integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from flashforge import FlashForgeClient
from flashforge.models import FFMachineInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PRINTER_MODEL_NAMES
from .util import async_close_flashforge_client

_LOGGER = logging.getLogger(__name__)

UNKNOWN_MODEL = "Unknown"


class FlashForgeDataUpdateCoordinator(DataUpdateCoordinator[FFMachineInfo]):
    """Class to manage fetching FlashForge printer data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FlashForgeClient,
        name: str,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.printer_name = name

    @property
    def device_model(self) -> str:
        """Return the human-readable model derived from the firmware-set PID."""
        if self.data is None:
            return UNKNOWN_MODEL
        pid = getattr(self.data, "pid", None)
        if pid is None:
            return UNKNOWN_MODEL
        return PRINTER_MODEL_NAMES.get(pid, UNKNOWN_MODEL)

    async def _async_update_data(self) -> FFMachineInfo:
        """Fetch data from the printer."""
        try:
            # Get machine status using HTTP API
            machine_info = await self.client.info.get()

            if machine_info is None:
                raise UpdateFailed("Failed to retrieve printer status")

            self.client.cache_details(machine_info)

            if not getattr(machine_info, "camera_stream_url", ""):
                detected_camera_stream = await self.client.detect_camera_stream()
                if detected_camera_stream:
                    machine_info.camera_stream_url = detected_camera_stream  # type: ignore[attr-defined]

            return machine_info

        except Exception as err:
            _LOGGER.error("Error communicating with printer %s: %s", self.printer_name, err)
            raise UpdateFailed(f"Error communicating with printer: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and cleanup resources."""
        await async_close_flashforge_client(self.client)

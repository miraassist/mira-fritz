"""What every entity of a FRITZ!Box shares: its device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FritzCoordinator


class FritzEntity(CoordinatorEntity[FritzCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FritzCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="FRITZ!Box",
            manufacturer="AVM",
            configuration_url=f"http://{coordinator.box.host}",
        )

"""Sensor platform for Gemstone Lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GemstoneConfigEntry
from .color_util import unpack
from .coordinator import GemstoneCoordinator
from .entity import GemstoneEntity, async_add_discovered_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GemstoneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a "now playing" sensor per controller."""
    async_add_discovered_entities(
        entry,
        async_add_entities,
        lambda coordinator, device_id: [GemstoneNowPlaying(coordinator, device_id)],
    )


class GemstoneNowPlaying(GemstoneEntity, SensorEntity):
    """Report what the controller is showing right now."""

    _attr_translation_key = "now_playing"
    _attr_icon = "mdi:lightbulb-on-outline"

    def __init__(self, coordinator: GemstoneCoordinator, device_id: str) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_now_playing"

    @property
    def native_value(self) -> str:
        """Return a short description of the current output."""
        state = self._state
        if not state.get("onState"):
            return "Off"
        if design := (state.get("architectural") or {}).get("name"):
            return design
        if pattern := (state.get("pattern") or {}).get("name"):
            return pattern
        color = state.get("color")
        if isinstance(color_b := state.get("colorB"), dict):
            color = color_b.get("value")
        if color is not None:
            red, green, blue, white = unpack(color) or (0, 0, 0, 0)
            return f"#{red:02X}{green:02X}{blue:02X}" + (f"+W{white}" if white else "")
        return "On"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the underlying detail."""
        state = self._state
        info = self._info
        hub = info.get("hub") or {}
        settings = self.coordinator.settings(self._device_id)
        color = state.get("color")
        if isinstance(color_b := state.get("colorB"), dict):
            color = color_b.get("value")
        return {
            "on_state": state.get("onState"),
            "design": (state.get("architectural") or {}).get("name"),
            "pattern": (state.get("pattern") or {}).get("name"),
            "color": color,
            "control": self.coordinator.control_transport(self._device_id),
            "local_ip": self.coordinator.local_host(self._device_id)
            or hub.get("localIp"),
            "firmware": settings.get("firmware") or info.get("firmware"),
            "outputs": settings.get("pixelOutputNames") or hub.get("outputNames"),
            "pixel_count": settings.get("pixelCount") or hub.get("pixelCount"),
            "rgbw_sequence": settings.get("rgbwSequence") or hub.get("rgbwSequence"),
            **self.coordinator.recovery_details(self._device_id),
            "color_rgbw": _rgbw(color),
            **{
                f"pattern_{key}": value
                for key, value in _pattern_details(state.get("pattern")).items()
            },
            "zone_patterns": self._zone_patterns(state.get("architectural")),
            "timer": _timer(state.get("timer")),
        }

    def _zone_patterns(self, design: Any) -> list[dict[str, Any]] | None:
        """Describe each zone's pattern in a playing design, named where known."""
        if not isinstance(design, dict) or not design.get("zonePatterns"):
            return None
        names = {
            zone.get("id"): zone.get("name")
            for zone in self.coordinator.zones(self._device_id)
        }
        return [
            {
                "zone_id": entry.get("zoneId"),
                "zone": names.get(entry.get("zoneId")),
                "pattern": pattern.get("name"),
                **_pattern_details(pattern),
            }
            for entry in design["zonePatterns"]
            if isinstance(entry, dict)
            for pattern in [_as_dict(entry.get("pattern"))]
        ]


def _as_dict(value: Any) -> dict[str, Any]:
    """Treat anything but a dict as empty, so a malformed record cannot raise."""
    return value if isinstance(value, dict) else {}


def _rgbw(value: Any) -> list[int] | None:
    """Convert a packed controller colour into Home Assistant's rgbw_color form."""
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return list(unpack(value) or ())


def _pattern_details(pattern: Any) -> dict[str, Any]:
    """Describe a pattern, keeping off pixels in the colour list.

    A colour of 0 is an unlit pixel, not a missing value: dropping it would lose
    the spacing of patterns such as "2 on, 4 off".
    """
    pattern = _as_dict(pattern)
    colors = pattern.get("colors")
    return {
        "colors": [_rgbw(color) for color in colors]
        if isinstance(colors, list)
        else None,
        "animation": pattern.get("animation"),
        "speed": pattern.get("speed"),
        "brightness": pattern.get("brightness"),
        "direction": pattern.get("direction"),
        "background_color": _rgbw(pattern.get("backgroundColor")),
    }


def _timer(timer: Any) -> dict[str, Any] | None:
    """Return the controller timer that started the current content, if any."""
    if not isinstance(timer, dict):
        return None
    return {key: timer.get(key) for key in ("on", "off", "sunset")}

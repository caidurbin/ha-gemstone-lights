"""The Now playing sensor exposes enough of the pattern to reproduce it elsewhere."""

from homeassistant.helpers import entity_registry as er

WARM_WHITE = 0xFF000000


async def _now_playing(hass, coordinator, vendor, state):
    vendor.states["hub"] = state
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "gemstone_lights", "hub_now_playing"
    )
    return hass.states.get(entity_id)


async def test_pattern_colours_keep_off_pixels_in_order(hass, loaded_entry, vendor):
    # Given a motionless "2 on, 4 off" pattern on the white channel.
    state = {
        "onState": True,
        "pattern": {
            "name": "2 on, 4 off Warm",
            "animation": "motionless",
            "colors": [WARM_WHITE, WARM_WHITE, 0, 0, 0, 0],
            "speed": 128,
            "brightness": 255,
            "direction": 0,
            "backgroundColor": 0,
        },
        "timer": {"id": "t1", "on": "sunset-60", "off": "23:55", "sunset": "16:53"},
    }
    # When the sensor reads the controller state.
    sensor = await _now_playing(hass, loaded_entry, vendor, state)
    # Then the palette, including its unlit pixels, is usable as rgbw_color values.
    assert sensor.state == "2 on, 4 off Warm"
    assert sensor.attributes["pattern_colors"] == [
        [0, 0, 0, 255],
        [0, 0, 0, 255],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    assert sensor.attributes["pattern_animation"] == "motionless"
    assert sensor.attributes["pattern_speed"] == 128
    assert sensor.attributes["pattern_brightness"] == 255
    assert sensor.attributes["pattern_direction"] == 0
    assert sensor.attributes["pattern_background_color"] == [0, 0, 0, 0]
    assert sensor.attributes["timer"] == {
        "on": "sunset-60",
        "off": "23:55",
        "sunset": "16:53",
    }
    assert sensor.attributes["zone_patterns"] is None


async def test_zoned_design_reports_each_zone_pattern(hass, loaded_entry, vendor):
    # Given a design playing different patterns on the controller's named zones.
    state = {
        "onState": True,
        "architectural": {
            "name": "Split",
            "zonePatterns": [
                {
                    "zoneId": "front",
                    "pattern": {
                        "name": "Red chase",
                        "animation": "chase",
                        "colors": [255, 0],
                        "speed": 200,
                        "brightness": 180,
                    },
                },
                {
                    "zoneId": "unknown",
                    "pattern": {"name": "Blue", "colors": [0xFF0000]},
                },
            ],
        },
    }
    # When the sensor reads the controller state.
    sensor = await _now_playing(hass, loaded_entry, vendor, state)
    # Then each zone's palette is reported, named when the zone is known.
    assert sensor.state == "Split"
    zones = sensor.attributes["zone_patterns"]
    assert zones[0]["zone_id"] == "front"
    assert zones[0]["zone"] == "Front"
    assert zones[0]["pattern"] == "Red chase"
    assert zones[0]["colors"] == [[255, 0, 0, 0], [0, 0, 0, 0]]
    assert zones[0]["animation"] == "chase"
    assert zones[0]["brightness"] == 180
    assert zones[1]["zone"] is None
    assert zones[1]["colors"] == [[0, 0, 255, 0]]
    assert sensor.attributes["pattern_colors"] is None


async def test_solid_colour_is_reported_as_rgbw(hass, loaded_entry, vendor):
    # Given a solid colour with some white mixed in.
    state = {"onState": True, "colorB": {"value": 0x40FF8000, "brightness": 90}}
    # When the sensor reads the controller state.
    sensor = await _now_playing(hass, loaded_entry, vendor, state)
    # Then the colour is unpacked in rgbw_color order and no pattern is claimed.
    assert sensor.attributes["color_rgbw"] == [0, 128, 255, 64]
    assert sensor.attributes["pattern_colors"] is None
    assert sensor.attributes["timer"] is None

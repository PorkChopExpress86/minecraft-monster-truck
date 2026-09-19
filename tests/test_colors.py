import json
from pathlib import Path

from PIL import Image

from scripts.make_placeholder_textures import BODY_COLORS, generate_entity_texture

ROOT = Path(__file__).resolve().parents[1]
COLORS = (
    "red", "blue", "green", "yellow", "black", "white",
    "orange", "magenta", "light_blue", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "brown"
)


def test_color_property_events_and_render_textures():
    entity = json.loads((ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json").read_text())["minecraft:entity"]
    assert entity["description"]["properties"]["blake:color"] == {
        "type": "int", "range": [0, 15], "default": 0, "client_sync": True,
    }
    client = json.loads((ROOT / "resource_packs/MonsterTruck_RP/entity/monster_truck.entity.json").read_text())["minecraft:client_entity"]["description"]
    controller = json.loads((ROOT / "resource_packs/MonsterTruck_RP/render_controllers/monster_truck.render_controllers.json").read_text())["render_controllers"]["controller.render.blake.monster_truck"]
    assert controller["textures"] == ["Array.colors[query.property('blake:color')]"]
    textures = controller["arrays"]["textures"]["Array.colors"]
    assert len(textures) == len(COLORS)
    for index, color in enumerate(COLORS):
        assert entity["events"]["blake:paint_" + color]["set_property"] == {"blake:color": index}
        alias = textures[index].split(".", 1)[1]
        texture = ROOT / "resource_packs/MonsterTruck_RP" / (client["textures"][alias] + ".png")
        assert texture.is_file()

def test_randomized_spawn_egg_event():
    entity = json.loads((ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json").read_text())["minecraft:entity"]
    events = entity.get("events", {})
    assert "blake:random_color_on_spawn" in events, "Must have blake:random_color_on_spawn event"
    random_event = events["blake:random_color_on_spawn"]
    assert "randomize" in random_event, "blake:random_color_on_spawn must randomize color"
    random_branches = random_event["randomize"]
    assert len(random_branches) == 16, f"Must have 16 randomize color branches, got {len(random_branches)}"
    assert "minecraft:entity_spawned" not in events, "Generic spawns and bare summons must retain default red"
    spawn_item = json.loads(
        (ROOT / "behavior_packs/MonsterTruck_BP/items/monster_truck_spawn_egg.item.json")
        .read_text(encoding="utf-8")
    )["minecraft:item"]
    assert spawn_item["components"]["minecraft:entity_placer"]["entity"] == (
        "blake:monster_truck<blake:random_color_on_spawn>"
    )


def test_generated_colors_preserve_red_and_non_body_pixels(tmp_path):
    texture_root = ROOT / "resource_packs/MonsterTruck_RP/textures/entity"
    with Image.open(texture_root / "monster_truck.png") as source:
        red = source.convert("RGBA")
    bodies = set()
    for color in COLORS:
        generated = tmp_path / (color + ".png")
        generate_entity_texture(generated, color)
        with Image.open(generated) as source:
            image = source.convert("RGBA")
        asset = texture_root / ("monster_truck.png" if color == "red" else "monster_truck_" + color + ".png")
        with Image.open(asset) as source:
            assert image.tobytes() == source.convert("RGBA").tobytes()
        bodies.add(image.getpixel((20, 20)))
        # Check color-matched wheel hub
        assert image.getpixel((19, 162)) == image.getpixel((20, 20))
        for y in range(256):
            for x in range(256):
                body_pixel = (0 <= x <= 120 and 0 <= y <= 60) or (96 <= x <= 160 and 64 <= y <= 120)
                hub_pixel = ((14 <= x <= 24 or 54 <= x <= 64 or 94 <= x <= 104 or 134 <= x <= 144) and 157 <= y <= 167)
                if (not body_pixel and not hub_pixel) or color == "red":
                    assert image.getpixel((x, y)) == red.getpixel((x, y))
    assert len(bodies) == len(COLORS)
    assert tuple(BODY_COLORS) == COLORS


def test_dye_painting_requires_sneaking_and_keeps_mounting():
    entity = json.loads((ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json").read_text())["minecraft:entity"]
    components = entity["components"]
    assert components["minecraft:rideable"]["seat_count"] == 2
    interactions = components["minecraft:interact"]["interactions"]
    assert len(interactions) == len(COLORS)
    for interaction, color in zip(interactions, COLORS):
        trigger = interaction["on_interact"]
        assert trigger["event"] == "blake:paint_" + color
        assert trigger["target"] == "self"
        assert trigger["filters"]["all_of"] == [
            {"test": "is_sneaking", "subject": "other", "value": True},
            {"test": "has_equipment", "subject": "other", "domain": "main_hand", "value": "minecraft:" + color + "_dye"},
        ]
        assert interaction["use_item"] is False


def test_live_harness_checks_every_explicit_spawn_color():
    harness = (ROOT / "testing/harness/assertions.js").read_text(encoding="utf-8")
    for color in COLORS:
        assert f'"{color}"' in harness
    assert 'triggerEvent("blake:spawn_" + colors[index])' in harness
    assert 'triggerEvent("blake:paint_" + colors[index])' not in harness

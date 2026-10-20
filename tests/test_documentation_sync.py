import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_COLORS = (
    "red", "blue", "green", "yellow", "black", "white",
    "orange", "magenta", "light_blue", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "brown"
)


def test_readme_and_recipe_guide_stats_match_entity_json():
    entity_path = ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json"
    entity = json.loads(entity_path.read_text(encoding="utf-8"))["minecraft:entity"]
    components = entity["components"]

    max_health = components["minecraft:health"]["max"]
    movement_value = components["minecraft:movement"]["value"]
    step_value = components["minecraft:variable_max_auto_step"]["controlled_value"]

    assert max_health == 20  # the heart gauge; Durability is 1,000 (ADR-0020)
    assert movement_value == 0.55
    assert step_value == 2.0

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "1,000 points" in readme
    assert "0.55" in readme
    assert "2 blocks" in readme
    assert "sixteen paint colors" in readme

    recipe_guide = (ROOT / "docs/RECIPE_GUIDE.md").read_text(encoding="utf-8")
    assert "1,000 points" in recipe_guide
    assert "0.55" in recipe_guide
    assert "2 Full Blocks" in recipe_guide


def test_readme_and_context_cover_all_sixteen_colors():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for color in EXPECTED_COLORS:
        formatted = color.replace("_", " ").title()
        assert formatted in readme, f"Color {formatted} missing from README"

    context = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "Sixteen-Color Palette" in context
    assert "Textured Color Swatches" in context
    assert "Sneak-Dye Repainting" in context
    assert "Randomized Spawn Egg Placement" in context
    assert "distinct from the randomized Creative spawn egg" in context


def test_proving_ground_checklist_covers_kinematics_and_sixteen_colors():
    pg = (ROOT / "docs/PROVING_GROUND.md").read_text(encoding="utf-8")
    assert "15. 16 Paint Colors" in pg
    assert "17. Handbrake Drift" in pg
    assert "18. Crush Stomp Landing" in pg
    assert "19. Shock Absorption" in pg
    assert "20. Amphibious Flotation" in pg
    assert "21. Shoreline Step-Up" in pg
    assert "22. Molten Tire Trample" in pg
    assert "23. Wood Demolition" in pg
    assert "24. Foliage Shearing" in pg
    assert "Dynamic Incline Pitch" in pg
    assert "Coordinated 4WS" in pg


def test_linux_testing_names_every_client_input_check():
    from scripts import client_checks
    doc = (ROOT / "docs/LINUX_TESTING.md").read_text(encoding="utf-8")
    missing = [name for name in client_checks.CHECKS if f"`{name}`" not in doc]
    assert not missing, f"docs/LINUX_TESTING.md does not name these Client Input Run checks: {missing}"


def test_acceptance_coverage_cites_only_node_tests_that_exist():
    # A citation is `<file>.test.mjs` followed by quoted test names (or parts of one), up to the next `, ; or |.
    doc = (ROOT / "docs/ACCEPTANCE_COVERAGE.md").read_text(encoding="utf-8")
    names = {path.name: re.findall(r'^test\("((?:[^"\\]|\\.)*)"', path.read_text(encoding="utf-8"), re.M)
             for path in (ROOT / "tests/js").glob("*.test.mjs")}
    cited = [(file, quote) for file, span in re.findall(r"`(\w+\.test\.mjs)`([^`;|]*)", doc)
             for quote in re.findall(r'"([^"]+)"', span)]
    assert cited, "the coverage doc cites node tests by name"
    missing = [f'{file} "{quote}"' for file, quote in cited
               if not any(quote in name for name in names.get(file, []))]
    assert not missing, f"docs/ACCEPTANCE_COVERAGE.md cites node tests that do not exist: {missing}"


def test_acceptance_coverage_names_every_client_check_and_opt_in_scenario():
    from scripts import client_checks
    doc = (ROOT / "docs/ACCEPTANCE_COVERAGE.md").read_text(encoding="utf-8")
    server = json.loads((ROOT / "testing/bedrock.json").read_text(encoding="utf-8"))["scenario_server"]
    names = list(client_checks.CHECKS) + server.get("opt_in_scenarios", [])
    missing = [name for name in names if f"`{name}`" not in doc]
    assert not missing, f"docs/ACCEPTANCE_COVERAGE.md names no evidence row for: {missing}"

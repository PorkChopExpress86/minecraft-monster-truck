import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_heavy_duty_stats_and_impact_protections():
    c = json.loads((ROOT/'behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json').read_text())['minecraft:entity']['components']
    # Health is the one-row heart gauge; durability.js charges Durability and owns the 75% combat
    # reduction (ADR-0020, tests/js/durability.test.mjs), so no trigger may scale damage a second time.
    assert c['minecraft:health'] == {'value':20,'max':20}
    triggers = c['minecraft:damage_sensor']['triggers']
    assert {'cause':'fall','deals_damage':'no'} in triggers
    assert not [t for t in triggers if 'damage_multiplier' in t]
    assert 'minecraft:area_attack' not in c, (
        'Scripted Speed-Scaled Tire Trample must be the only contact-damage authority'
    )
    # Speed-scaled Tire Trample damage: tests/js/truck_tick.test.mjs.

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_heavy_duty_stats_and_impact_protections():
    c = json.loads((ROOT/'behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json').read_text())['minecraft:entity']['components']
    assert c['minecraft:health'] == {'value':1000,'max':1000}
    triggers = c['minecraft:damage_sensor']['triggers']
    assert {'cause':'fall','deals_damage':'no'} in triggers
    for cause in ['entity_attack','projectile','entity_explosion','block_explosion']:
        assert {'cause':cause,'deals_damage':'yes','damage_multiplier':0.25} in triggers
    assert 'minecraft:area_attack' not in c, (
        'Scripted Speed-Scaled Tire Trample must be the only contact-damage authority'
    )
    main = (ROOT/'behavior_packs/MonsterTruck_BP/scripts/main.js').read_text(encoding='utf-8')
    assert 'calculateTrampleDamage(effectiveSpeed)' in main

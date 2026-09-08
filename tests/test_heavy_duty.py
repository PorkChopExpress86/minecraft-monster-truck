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
    attack = c['minecraft:area_attack']
    assert attack['damage_per_tick'] == 40
    assert attack['damage_cooldown'] == 0.5
    filters = attack['entity_filter']['all_of']
    assert {'test':'is_moving','subject':'self','value':True} in filters
    for family in ['player','vehicle']:
        assert {'test':'is_family','subject':'other','value':family,'operator':'!='} in filters
    assert {'test':'is_tamed','subject':'other','value':False} in filters

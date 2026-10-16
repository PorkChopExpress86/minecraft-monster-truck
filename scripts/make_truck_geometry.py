"""Build the lifted pickup mesh using explicit atlas swatches (Minecraft units)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWATCHES = {'paint': (20,20), 'shade': (110,80), 'glass': (20,80), 'rubber': (10,155), 'tread': (0,144), 'metal': (20,205), 'lamp': (40,220)}

def cube(origin, size, material, **extra):
    u,v = SWATCHES[material]
    return {'origin':origin, 'size':size, 'uv':{face:{'uv':[u,v],'uv_size':[1,1]} for face in ['north','south','east','west','up','down']}, **extra}

def generate():
    body=[]
    def add(o,s,m='paint',**kw):body.append(cube(o,s,m,**kw))
    # Raised floor, sloped hood, cab doors, pillars and elevated roof; open rear cargo bed.
    add([-14,24,-26],[28,4,52])
    # Sloped hood: lower nose (Z -26..-17, Y 28..31) and cowl (Z -17..-9, Y 28..33)
    add([-14,28,-26],[28,3,9]);add([-14,28,-17],[28,5,8])
    # Interior dashboard at cowl
    add([-12,28,-9],[24,4,2],'rubber')
    add([-14,28,-9],[2,7,21]);add([12,28,-9],[2,7,21])
    # Elevated roof at Y 46..48 ensuring full vertical headroom for seated riders
    add([-14,46,-9],[28,2,21])
    for x in [-14,12]:
        for z in [-9,10]:add([x,34,z],[2,12,2])
    add([-12,34,-8.5],[24,12,0.5],'glass')
    add([-12,34,10.5],[24,12,0.5],'glass')
    # Side windows are open so riders remain visible.
    add([-14,28,12],[2,6,14]);add([12,28,12],[2,6,14]);add([-12,28,24],[24,6,2])
    add([-12,28,12],[24,1,12],'rubber')
    # Fitted seat cushions aligned with seat coordinate Y 1.15 (18.4 units) on floor
    add([2,24,2],[9,3,7],'rubber');add([-11,24,2],[9,3,7],'rubber')
    # Grille, headlights, bumpers, rear lamps and running boards aligned with sloped nose.
    add([-9,28,-26.6],[18,3,1],'rubber')
    for y in [29,30]:add([-8,y,-27],[16,0.5,0.5],'metal')
    for x in [-13,9]:add([x,28.5,-27],[4,2.5,1],'lamp')
    add([-16,23,-28],[32,3,3],'metal');add([-16,23,25],[32,3,3],'metal')
    for x in [-17,14]:add([x,23,-8],[3,2,20],'metal')
    # Bold stepped contrasting side graphics.
    for x in [-14.1,14]:
        for z,y in [(-5,29),(-2,30),(1,31),(4,30),(7,29)]:add([x,y,z],[0.1,2,3],'shade')

    # Realistic Exposed V8 Engine & Supercharger Blower
    # Engine Block sitting in the front bay under cowl/hood
    add([-7,27,-19],[14,7,10],'metal')
    # Twin valve covers (angled look)
    add([-8,33,-19],[4,2.5,9],'shade');add([4,33,-19],[4,2.5,9],'shade')
    # Blower / Supercharger case rising through the hood
    add([-4.5,33,-18],[9,4.5,8],'metal')
    # Prominent triple-butterfly scoop air intake
    add([-4,37.5,-19],[8,3,7],'metal')
    # Scoop intake openings
    add([-3.5,38,-19.2],[7,2,0.2],'rubber')
    # Dual side exhaust zoomie headers emerging under cab sides
    for side,x in [(-1,-14.5),(1,12.5)]:
        for z_off in [-6,-3,0,3]:
            add([x,22,z_off],[2,2.5,2],'metal')
            add([x+(0.5 if side>0 else -0.5),21,z_off+0.5],[2,1.5,1],'rubber')

    # Cab interior roll cage in roll_cage bone
    cage=[]
    def add_cage(o,s,m='metal',**kw):cage.append(cube(o,s,m,**kw))
    for x in [-12.5,10.5]:
        for z in [-8,9]:add_cage([x,28,z],[2,18,2],'metal')
    for x in [-12.5,10.5]:add_cage([x,44,-8],[2,2,19],'metal')
    for z in [-8,9]:add_cage([-12.5,44,z],[25,2,2],'metal')
    # Diagonal bed roll-bar supports
    for x in [-12.5,10.5]:add_cage([x,28,11],[2,16,11],'metal')

    # Heavy-duty tubular chassis frame and realistic monster truck suspension
    frame=[]
    # Main longitudinal frame rails
    for x in [-9,7]:frame.append(cube([x,17,-23],[2,5,46],'rubber'))
    # Frame crossmembers
    for z in [-20,-4,12]:frame.append(cube([-7,19,z],[14,3,3],'metal'))

    # Heavy duty live axles and differential pumpkin housings
    for z in [-18,18]:
        frame.append(cube([-21,11,z-1.5],[42,3,3],'metal'))
        frame.append(cube([-4,9,z-3],[8,6,6],'rubber'))
        # 4-Link Suspension Control Arms: lower triangulated trailing arms from center cradle to axles
        for side,x_mount in [(-1,-7),(1,5)]:
            # Lower control arm
            frame.append(cube([x_mount,13,-14 if z<0 else 2],[2,2,14],'metal'))
            # Upper triangulated link
            frame.append(cube([x_mount+side,16,-10 if z<0 else 4],[2,2,10],'metal'))
        # Nitrogen dual-reservoir piggyback coilover shocks (two per corner: main body + reservoir canister)
        for x in [-12,10]:
            # Main high-travel coil shock cylinder
            frame.append(cube([x,11.5,z-1.5],[2.5,13.5,3],'metal'))
            # Coil spring outer wrap detail
            frame.append(cube([x-0.2,14,z-1.7],[2.9,8,3.4],'shade'))
            # Piggyback remote nitrogen reservoir
            frame.append(cube([x+(1.5 if x>0 else -1.5),16,z-1],[1.5,7,2],'metal'))
        # Heavy-duty steering tie rod across axle
        frame.append(cube([-19,13.5,z-2],[38,1.5,1.5],'metal'))

    bones=[
        {'name':'root','pivot':[0,0,0]},
        {'name':'body','parent':'root','pivot':[0,24,0],'cubes':body},
        {'name':'roll_cage','parent':'body','pivot':[0,24,0],'cubes':cage},
        {'name':'suspension','parent':'root','pivot':[0,0,0],'cubes':frame}
    ]

    for name,x,z in [('wheel_fl',20,-18),('wheel_fr',-20,-18),('wheel_rl',20,18),('wheel_rr',-20,18)]:
        pivot=[x,12,z];parts=[]
        steer_name = name.replace('wheel_', 'steer_')
        bones.append({'name':steer_name,'parent':'root','pivot':pivot})
        # Two intersecting squares form a chunky octagonal tire section.
        for angle in [0,45]:parts.append(cube([x-6,3.5,z-8.5],[12,17,17],'rubber',pivot=pivot,rotation=[angle,0,0]))
        for angle in range(0,360,30):parts.append(cube([x-6.5,22.5,z-2.5],[13,2,5],'tread',pivot=pivot,rotation=[angle,0,0]))
        outer=x+6 if x>0 else x-7
        parts.append(cube([outer,7,z-5],[1,10,10],'metal'))
        parts.append(cube([outer+(0.1 if x>0 else -0.1),9,z-3],[1,6,6],'shade'))
        bones.append({'name':name,'parent':steer_name,'pivot':pivot,'cubes':parts})
    mesh={'format_version':'1.12.0','minecraft:geometry':[{'description':{'identifier':'geometry.blake.monster_truck','texture_width':256,'texture_height':256,'visible_bounds_width':6,'visible_bounds_height':5,'visible_bounds_offset':[0,2,0]},'bones':bones}]}
    (ROOT/'resource_packs/MonsterTruck_RP/models/entity/monster_truck.geo.json').write_text(json.dumps(mesh,indent=2)+'\n')

if __name__ == '__main__':generate()

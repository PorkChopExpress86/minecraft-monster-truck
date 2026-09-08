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
    # Raised floor, hood, cab doors, pillars and roof; open rear cargo bed.
    add([-14,24,-26],[28,4,52]);add([-14,28,-26],[28,6,17])
    add([-14,28,-9],[2,7,21]);add([12,28,-9],[2,7,21])
    add([-14,43,-9],[28,2,21])
    for x in [-14,12]:
        for z in [-9,10]:add([x,34,z],[2,9,2])
    add([-12,35,-8.5],[24,8,0.5],'glass')
    add([-12,35,10.5],[24,8,0.5],'glass')
    # Side windows are open so riders remain visible.
    add([-14,28,12],[2,6,14]);add([12,28,12],[2,6,14]);add([-12,28,24],[24,6,2])
    add([-12,28,12],[24,1,12],'rubber')
    add([-11,28,7],[9,7,3],'rubber');add([2,28,7],[9,7,3],'rubber')
    # Grille, headlights, bumpers, rear lamps and running boards.
    add([-9,28,-26.6],[18,5,1],'rubber')
    for y in [29,31]:add([-8,y,-27],[16,0.5,0.5],'metal')
    for x in [-13,9]:add([x,29,-27],[4,4,1],'lamp')
    add([-16,23,-28],[32,3,3],'metal');add([-16,23,25],[32,3,3],'metal')
    for x in [-17,14]:add([x,23,-8],[3,2,20],'metal')
    # Bold stepped contrasting side graphics.
    for x in [-14.1,14]:
        for z,y in [(-5,29),(-2,30),(1,31),(4,30),(7,29)]:add([x,y,z],[0.1,2,3],'shade')
    frame=[]
    for x in [-9,7]:frame.append(cube([x,17,-23],[2,5,46],'rubber'))
    for z in [-18,18]:
        frame.append(cube([-21,11,z-1.5],[42,3,3],'metal'))
        frame.append(cube([-4,9,z-3],[8,6,6],'rubber'))
        for x in [-11,9]:frame.append(cube([x,12,z-1],[2,12,2],'metal'))
    bones=[{'name':'root','pivot':[0,0,0]}, {'name':'body','parent':'root','pivot':[0,24,0],'cubes':body}, {'name':'roll_cage','parent':'body','pivot':[0,24,0]}, {'name':'suspension','parent':'root','pivot':[0,0,0],'cubes':frame}]
    for name,x,z in [('wheel_fl',20,-18),('wheel_fr',-20,-18),('wheel_rl',20,18),('wheel_rr',-20,18)]:
        pivot=[x,12,z];parts=[]
        # Two intersecting squares form a chunky octagonal tire section.
        for angle in [0,45]:parts.append(cube([x-6,3.5,z-8.5],[12,17,17],'rubber',pivot=pivot,rotation=[angle,0,0]))
        for angle in range(0,360,30):parts.append(cube([x-6.5,22.5,z-2.5],[13,2,5],'tread',pivot=pivot,rotation=[angle,0,0]))
        outer=x+6 if x>0 else x-7
        parts.append(cube([outer,7,z-5],[1,10,10],'metal'))
        parts.append(cube([outer+(0.1 if x>0 else -0.1),9,z-3],[1,6,6],'shade'))
        bones.append({'name':name,'parent':'root','pivot':pivot,'cubes':parts})
    mesh={'format_version':'1.12.0','minecraft:geometry':[{'description':{'identifier':'geometry.blake.monster_truck','texture_width':256,'texture_height':256,'visible_bounds_width':6,'visible_bounds_height':5,'visible_bounds_offset':[0,2,0]},'bones':bones}]}
    (ROOT/'resource_packs/MonsterTruck_RP/models/entity/monster_truck.geo.json').write_text(json.dumps(mesh,indent=2)+'\n')

if __name__ == '__main__':generate()

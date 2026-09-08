import os
from pathlib import Path
from PIL import Image, ImageDraw

BODY_COLORS = {
    "red": ((180, 30, 30), (120, 15, 15), (160, 25, 25), (100, 10, 10)),
    "blue": ((35, 75, 190), (20, 40, 125), (25, 60, 170), (15, 30, 105)),
    "green": ((40, 160, 55), (20, 100, 30), (30, 140, 45), (15, 80, 20)),
    "yellow": ((235, 205, 30), (165, 135, 15), (215, 180, 25), (145, 115, 10)),
    "black": ((40, 40, 45), (15, 15, 20), (30, 30, 35), (10, 10, 15)),
    "white": ((235, 235, 240), (165, 165, 175), (215, 215, 225), (145, 145, 155)),
}


def generate_entity_texture(output_path: Path, color="red"):
    body, body_outline, hood, hood_outline = BODY_COLORS[color]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Body lower chassis (UV [0, 0] to [120, 60])
    draw.rectangle([0, 0, 120, 60], fill=(*body, 255), outline=(*body_outline, 255))
    
    # Cab / Windows (UV [0, 64] to [90, 120])
    draw.rectangle([0, 64, 90, 120], fill=(80, 150, 220, 220), outline=(40, 80, 140, 255))
    
    # Hood / Front (UV [96, 64] to [160, 120])
    draw.rectangle([96, 64, 160, 120], fill=(*hood, 255), outline=(*hood_outline, 255))
    
    # Wheels FL, FR, RL, RR (UV around [0, 144] ... [160, 180])
    draw.rectangle([0, 144, 38, 180], fill=(30, 30, 30, 255), outline=(60, 60, 60, 255))
    draw.rectangle([40, 144, 78, 180], fill=(30, 30, 30, 255), outline=(60, 60, 60, 255))
    draw.rectangle([80, 144, 118, 180], fill=(30, 30, 30, 255), outline=(60, 60, 60, 255))
    draw.rectangle([120, 144, 158, 180], fill=(30, 30, 30, 255), outline=(60, 60, 60, 255))
    
    # Roll cage / Metal accents (UV [0, 190] to [60, 240])
    draw.rectangle([0, 190, 60, 240], fill=(165, 175, 185, 255), outline=(80, 90, 100, 255))
    
    draw.rectangle([40, 220, 45, 225], fill=(255, 240, 180, 255))
    img.save(output_path, "PNG")
    print(f"Generated entity texture: {output_path}")

def generate_spawn_egg(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    
    # Draw pixel-art monster truck silhouette
    pixels = img.load()
    red = (190, 30, 30, 255)
    dark_red = (130, 20, 20, 255)
    glass = (100, 180, 240, 255)
    tire = (20, 20, 20, 255)
    hub = (200, 200, 50, 255)
    
    # Cab / Body
    for x in range(4, 11):
        pixels[x, 5] = dark_red
    for x in range(3, 13):
        pixels[x, 6] = red
    for x in range(2, 14):
        pixels[x, 7] = red
    for x in range(2, 14):
        pixels[x, 8] = red
        
    # Windshield
    pixels[5, 6] = glass
    pixels[6, 6] = glass
    pixels[7, 6] = glass
    
    # Big Monster Truck Wheels
    # Front Wheel (x: 2..5, y: 9..12)
    for x in range(2, 6):
        for y in range(9, 13):
            pixels[x, y] = tire
    pixels[3, 10] = hub
    pixels[4, 10] = hub
    
    # Rear Wheel (x: 10..13, y: 9..12)
    for x in range(10, 14):
        for y in range(9, 13):
            pixels[x, y] = tire
    pixels[11, 10] = hub
    pixels[12, 10] = hub
    
    img.save(output_path, "PNG")
    print(f"Generated spawn egg: {output_path}")

def generate_pack_icon(output_path: Path, title: str):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (64, 64), (40, 40, 45, 255))
    draw = ImageDraw.Draw(img)
    
    # Border
    draw.rectangle([0, 0, 63, 63], outline=(220, 180, 20, 255), width=2)
    # Truck body silhouette
    draw.rectangle([14, 20, 50, 38], fill=(190, 30, 30, 255), outline=(130, 20, 20, 255))
    draw.rectangle([22, 14, 42, 22], fill=(80, 150, 220, 255))
    # Big wheels
    draw.ellipse([8, 32, 26, 50], fill=(20, 20, 20, 255), outline=(220, 180, 20, 255))
    draw.ellipse([38, 32, 56, 50], fill=(20, 20, 20, 255), outline=(220, 180, 20, 255))
    
    img.save(output_path, "PNG")
    print(f"Generated pack icon: {output_path}")

def generate_all(repo_root=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    rp_textures = root / "resource_packs" / "MonsterTruck_RP" / "textures"
    bp_root = root / "behavior_packs" / "MonsterTruck_BP"
    rp_root = root / "resource_packs" / "MonsterTruck_RP"
    
    generate_entity_texture(rp_textures / "entity" / "monster_truck.png")
    for color in BODY_COLORS:
        if color != "red":
            generate_entity_texture(rp_textures / "entity" / f"monster_truck_{color}.png", color)
    generate_spawn_egg(rp_textures / "items" / "monster_truck_spawn_egg.png")
    generate_pack_icon(bp_root / "pack_icon.png", "BP")
    generate_pack_icon(rp_root / "pack_icon.png", "RP")

if __name__ == "__main__":
    generate_all()

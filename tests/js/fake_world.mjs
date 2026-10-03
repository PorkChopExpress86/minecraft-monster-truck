// In-memory stand-ins for the Script API objects tickTruck touches: a block grid dimension,
// entities that record what the add-on did to them, and a truck whose motion the test sets
// each tick (the engine's physics is not simulated). Shapes follow the typedefs in
// behavior_packs/MonsterTruck_BP/scripts/truck_tick.js.

const key = (x, y, z) => `${Math.floor(x)},${Math.floor(y)},${Math.floor(z)}`;

export function createFakeDimension() {
  const blocks = new Map();
  const dimension = {
    entities: [],
    particles: [],
    sounds: [],
    commands: [],
    setBlock(x, y, z, typeId) {
      blocks.set(key(x, y, z), typeId);
    },
    typeAt(x, y, z) {
      return blocks.get(key(x, y, z)) ?? "minecraft:air";
    },
    // Fill a horizontal square of blocks at height y centred on (cx, cz).
    fillLayer(y, typeId, cx = 0, cz = 0, radius = 12) {
      for (let x = cx - radius; x <= cx + radius; x++) {
        for (let z = cz - radius; z <= cz + radius; z++) blocks.set(key(x, y, z), typeId);
      }
    },
    getBlock(location) {
      const k = key(location.x, location.y, location.z);
      const typeId = blocks.get(k) ?? "minecraft:air";
      return {
        typeId,
        isAir: typeId === "minecraft:air",
        setType(type) {
          blocks.set(k, type);
        },
      };
    },
    getEntities(options = {}) {
      return dimension.entities.filter((entity) => {
        if (options.type && entity.typeId !== options.type) return false;
        if (options.location && options.maxDistance !== undefined) {
          const d = Math.hypot(
            entity.location.x - options.location.x,
            entity.location.y - options.location.y,
            entity.location.z - options.location.z
          );
          if (d > options.maxDistance) return false;
        }
        return true;
      });
    },
    spawnParticle(effectName, location) {
      dimension.particles.push({ effectName, location });
    },
    playSound(soundId, location, options) {
      dimension.sounds.push({ soundId, location, options });
    },
    runCommand(commandString) {
      dimension.commands.push(commandString);
      const match = /^setblock (-?\d+) (-?\d+) (-?\d+) air destroy$/.exec(commandString);
      if (match) blocks.set(key(+match[1], +match[2], +match[3]), "minecraft:air");
    },
  };
  return dimension;
}

let nextId = 1;

export function createFakeEntity({ typeId = "minecraft:zombie", location = { x: 0, y: 0, z: 0 }, id } = {}) {
  const entity = {
    id: id ?? `entity-${nextId++}`,
    typeId,
    isValid: true,
    location: { ...location },
    impulses: [],
    damage: [],
    fire: [],
    applyImpulse(vector) {
      entity.impulses.push({ ...vector });
    },
    applyDamage(amount, options) {
      entity.damage.push({ amount, options });
      return true;
    },
    setOnFire(seconds, useEffects) {
      entity.fire.push({ seconds, useEffects });
      return true;
    },
  };
  return entity;
}

export function createFakePlayer({ id, location = { x: 0, y: 0, z: 0 }, isSneaking = false } = {}) {
  const player = createFakeEntity({ typeId: "minecraft:player", location, id });
  Object.assign(player, {
    isSneaking,
    extinguished: 0,
    teleports: [],
    extinguishFire() {
      player.extinguished += 1;
      return true;
    },
    teleport(location, options) {
      player.teleports.push({ location, options });
    },
  });
  return player;
}

export function createFakeTruck({ location = { x: 0.5, y: 61, z: 0.5 }, yaw = 0, isOnGround = true, riders = [] } = {}) {
  const truck = createFakeEntity({ typeId: "blake:monster_truck", location });
  const seated = [...riders];
  Object.assign(truck, {
    velocity: { x: 0, y: 0, z: 0 },
    rotation: { x: 0, y: yaw },
    isOnGround,
    properties: {},
    cleared: 0,
    seated,
    getVelocity() {
      return { ...truck.velocity };
    },
    clearVelocity() {
      truck.cleared += 1;
    },
    getRotation() {
      return { ...truck.rotation };
    },
    setRotation(rotation) {
      truck.rotation = { ...rotation };
    },
    setProperty(name, value) {
      truck.properties[name] = value;
    },
    getComponent(componentId) {
      if (componentId !== "minecraft:rideable") return undefined;
      return {
        getRiders: () => [...seated],
        addRider(rider) {
          if (!seated.includes(rider)) seated.push(rider);
          return true;
        },
      };
    },
    // Engine detaches a rider (or the rider sneaks out).
    detach(rider) {
      const i = seated.indexOf(rider);
      if (i >= 0) seated.splice(i, 1);
    },
    // Place the truck where the engine moved it this tick.
    moveTo(location, { velocity, isOnGround } = {}) {
      truck.location = { ...truck.location, ...location };
      if (velocity) truck.velocity = { x: 0, y: 0, z: 0, ...velocity };
      if (isOnGround !== undefined) truck.isOnGround = isOnGround;
    },
  });
  return truck;
}

// Driver input seam double: every driver presses the same keys.
export function fixedInput({ forward = 0, strafe = 0, handbrake = false } = {}) {
  return {
    movement: () => ({ x: strafe, y: forward }),
    handbrake: () => handbrake,
  };
}

// Everything tickTruck needs from outside the truck and dimension, as main.js supplies it.
export function createTickInput({ driverInput = fixedInput(), entities = [] } = {}) {
  return {
    driverInput,
    getEntity: (id) => entities.find((entity) => entity.id === id),
    protectedRiders: new Map(),
    hitCooldowns: new Map(),
  };
}

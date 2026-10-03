// A stand-in for the @minecraft/server module so node can import main.js. Importing this file
// registers a resolve hook that maps "@minecraft/server" to it; import it before main.js.
// `fake` records what main.js subscribed and lets tests place dimensions and entities.
import { registerHooks } from "node:module";

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "@minecraft/server") return { url: import.meta.url, shortCircuit: true };
    return nextResolve(specifier, context);
  },
});

export const fake = {
  intervals: [],
  runs: [],
  hurtHandlers: [],
  afterEventSubscriptions: [],
  dimensions: {},
  entities: new Map(),
};

export const ButtonState = { Pressed: "Pressed", Released: "Released" };
export const InputButton = { Jump: "Jump", Sneak: "Sneak" };

export class ItemStack {
  constructor(typeId, amount = 1) {
    this.typeId = typeId;
    this.amount = amount;
  }
}

export const system = {
  currentTick: 1000,
  runInterval(callback) {
    fake.intervals.push(callback);
    return fake.intervals.length;
  },
  run(callback) {
    fake.runs.push(callback);
    return fake.runs.length;
  },
};

export const world = {
  getDimension(id) {
    const dimension = fake.dimensions[id];
    if (!dimension) throw new Error(`no dimension ${id}`);
    return dimension;
  },
  getEntity(id) {
    return fake.entities.get(id);
  },
  beforeEvents: {
    entityHurt: {
      subscribe(handler) {
        fake.hurtHandlers.push(handler);
        return handler;
      },
    },
  },
  // Any after-event main.js subscribes to is recorded by name.
  afterEvents: new Proxy({}, {
    get(_, name) {
      return {
        subscribe(handler) {
          fake.afterEventSubscriptions.push(String(name));
          return handler;
        },
      };
    },
  }),
};

// Run main.js's tick loop once at the next tick number.
export function runTick() {
  system.currentTick += 1;
  for (const callback of fake.intervals) callback();
}

// Deliver a before-hurt event to main.js's handler; returns the event so tests read .cancel.
export function hurt(hurtEntity, cause, { damage = 4, damagingEntity } = {}) {
  const event = { hurtEntity, damage, damageSource: { cause, damagingEntity }, cancel: false };
  for (const handler of fake.hurtHandlers) handler(event);
  return event;
}

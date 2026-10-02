import { system, world, GameMode } from "@minecraft/server";
import { spawnSimulatedPlayer } from "@minecraft/server-gametest";
import { run } from "./run_config.js";
import { park, resetArena, wait } from "./arena.js";
import { SCENARIOS } from "./scenarios.js";

// Test-only Scenario Run driver (ADR-0016). Never part of the distributable add-on.
const emit = (status, details) => console.warn("[SCENARIO]" + JSON.stringify({
  run_id: run.run_id, status, ...details,
}));

async function loadArena(dimension) {
  const spawn = world.getDefaultSpawnLocation();
  const center = { x: Math.floor(spawn.x), y: 0, z: Math.floor(spawn.z) };
  dimension.runCommand(`tickingarea add circle ${center.x} 0 ${center.z} 4 scenario_arena true`);
  for (let tick = 0; tick < 400 && !dimension.isChunkLoaded(center); tick += 5) await wait(5);
  const top = dimension.getTopmostBlock({ x: center.x, z: center.z });
  if (!top) throw new Error("Scenario arena chunks never loaded");
  return { x: center.x + 0.5, y: top.location.y + 1, z: center.z + 0.5 };
}

world.afterEvents.worldLoad.subscribe(() => system.run(async () => {
  const dimension = world.getDimension("overworld");
  const extras = [];
  let driver;
  try {
    const origin = await loadArena(dimension);
    // Survival, so fall, fire, and lava protection are observable on the rider.
    driver = spawnSimulatedPlayer({ dimension, ...origin }, "SimulatedDriver", GameMode.Survival);
    const spawnPlayer = name => {
      const player = spawnSimulatedPlayer({ dimension, ...origin }, name, GameMode.Survival);
      extras.push(player);
      return player;
    };
    await wait(20);
    for (const name of run.scenarios) {
      park(driver, origin);
      resetArena(dimension, origin);
      driver.getComponent("minecraft:health").resetToMaxValue();
      driver.extinguishFire();
      await wait(10);
      try {
        const scenario = SCENARIOS[name];
        if (!scenario) throw new Error("Unknown scenario: " + name);
        const checks = await scenario({ dimension, origin, driver, run, wait, spawnPlayer });
        emit("PASS", { scenario: name, checks });
      } catch (error) {
        emit("FAIL", { scenario: name, error: String(error) });
      } finally {
        while (extras.length) extras.pop().disconnect();
      }
    }
    emit("DONE", {});
  } catch (error) {
    emit("FAIL", { scenario: "setup", error: String(error) });
    emit("DONE", {});
  } finally {
    driver?.disconnect();
  }
}));

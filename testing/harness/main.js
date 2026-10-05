import { system, world } from "@minecraft/server";
import { run } from "./run_config.js";
import { assertAddon } from "./assertions.js";
import { startClientProbe } from "./client_probe.js";

const emit = (status, details) => console.warn("[ADDON_TEST]" + JSON.stringify({
  run_id: run.run_id, entity_id: run.entity_id, status, ...details,
}));

// A player supplies a loaded chunk. The Python runner bounds the overall wait.
world.afterEvents.worldLoad.subscribe(() => {
  // A Client Input Run drives the world itself over its WebSocket; the harness only reports state.
  if (run.client_probe) {
    startClientProbe(run);
    return;
  }
  const timer = system.runInterval(async () => {
    const player = world.getAllPlayers()[0];
    if (!player) return;
    system.clearRun(timer);
    try {
      const result = await assertAddon(player, run);
      // Give the client time to load entity resources before cleanup and PASS.
      system.runTimeout(() => {
        try {
          if (!run.showcase) result.cleanup();
          emit("PASS", { checks: result.checks });
        } catch (error) {
          emit("FAIL", { error: String(error) });
        }
      }, 60);
    } catch (error) {
      emit("FAIL", { error: String(error) });
    }
  }, 20);
});

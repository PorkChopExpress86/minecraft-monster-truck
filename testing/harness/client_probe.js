import { system, world } from "@minecraft/server";

// Client Input Run probe (ADR-0019). The run reads the real client's world over a WebSocket, where
// querytarget gives positions and facing but not who rides what, so each tick this publishes the player's
// seat to scoreboard fake players the run can query:
//   riding   - 0 when the player is not riding a truck, else the seat index + 1
//   lost     - ticks the player has spent out of a truck since the run last set it to 0
//   sneaking - 1 while the game reports the player sneaking (the Sneak key reached it)
//   look     - the player's yaw in whole degrees, as scripts see it
//   sneak_button - 1 while inputInfo reports the Sneak button pressed
//   jump     - 1 while inputInfo reports the Jump button pressed (Space, the handbrake)
export const OBJECTIVE = "mt_probe";

export function startClientProbe(run) {
  const objective = world.scoreboard.getObjective(OBJECTIVE) ?? world.scoreboard.addObjective(OBJECTIVE);
  objective.setScore("riding", 0);
  objective.setScore("lost", 0);
  system.runInterval(() => {
    const player = world.getAllPlayers()[0];
    if (!player) return;
    let seat = 0;
    try {
      const vehicle = player.getComponent("minecraft:riding")?.entityRidingOn;
      if (vehicle?.typeId === run.entity_id) {
        seat = vehicle.getComponent("minecraft:rideable").getRiders().findIndex(rider => rider?.id === player.id) + 1;
      }
    } catch {
      seat = 0;
    }
    objective.setScore("riding", seat);
    if (seat === 0) objective.addScore("lost", 1);
    objective.setScore("sneaking", player.isSneaking ? 1 : 0);
    objective.setScore("look", Math.round(player.getRotation().y));
    let sneakButton = 0;
    try {
      sneakButton = player.inputInfo.getButtonState("Sneak") === "Pressed" ? 1 : 0;
    } catch {
      sneakButton = -1;
    }
    objective.setScore("sneak_button", sneakButton);
    let jump = 0;
    try {
      jump = player.inputInfo.getButtonState("Jump") === "Pressed" ? 1 : 0;
    } catch {
      jump = -1;
    }
    objective.setScore("jump", jump);
  }, 1);
}

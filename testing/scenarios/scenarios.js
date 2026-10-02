// Mechanic scenarios for Scenario Runs. Each takes { dimension, origin, driver, run, wait }
// and resolves to a list of passed checks or throws with the failed expectation.

async function smoke({ dimension, origin, driver, run, wait }) {
  const checks = [];
  if (!driver.isValid) throw new Error("Simulated Driver did not join");
  checks.push("simulated driver joined");
  const truck = dimension.spawnEntity(run.entity_id, { x: origin.x + 4, y: origin.y, z: origin.z });
  try {
    await wait(10);
    if (!truck.isValid || truck.typeId !== run.entity_id) throw new Error("Truck did not spawn");
    checks.push("spawned " + truck.typeId);
    const rideable = truck.getComponent("minecraft:rideable");
    if (rideable?.seatCount !== 2) throw new Error("Unexpected seat count: " + rideable?.seatCount);
    checks.push("seat count 2");
    return checks;
  } finally {
    if (truck.isValid) truck.remove();
  }
}

export const SCENARIOS = { smoke };

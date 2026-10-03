// Truck dimensions and angle limits shared by the add-on scripts. Values that also live in
// the entity JSON, vehicle.config.json, or the resource-pack animations are checked against
// them by tests/test_geometry_sync.py. Lengths are blocks, angles degrees.

// Body footprint used for Tire Trample contact (collision_box width, nose-to-tail length).
export const TRUCK_WIDTH = 2.25;
export const TRUCK_LENGTH = 3.6;
// How far outside the footprint a mob still counts as under the tires.
export const CONTACT_PERIMETER = 1.6;

// Dynamic Incline Pitch samples the ground under the front and rear axles.
export const PITCH_AXLE_SPAN = 2.25;
export const AXLE_OFFSET = PITCH_AXLE_SPAN / 2;

// Wheelbase of the driving bicycle model; sets the turning radius. Distinct from
// PITCH_AXLE_SPAN on purpose: it was tuned for steering feel, not measured off the model.
export const DRIVING_WHEELBASE = 3.0;

// Synced entity property ranges: blake:steer_angle and blake:pitch_angle.
export const MAX_STEER_DEGREES = 26;
export const MAX_PITCH_DEGREES = 35;
// Coordinated Four-Wheel Steering: the RP animation counter-steers the rear wheels by this
// share of the front angle (18 degrees at full lock).
export const REAR_STEER_RATIO = 18.0 / 26.0;

// monster_truck.entity.json minecraft:friction_modifier; the engine multiplies ground
// friction by it (docs/agents/bedrock-physics.md).
export const FRICTION_MODIFIER = 1.15;

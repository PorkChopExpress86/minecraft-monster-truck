# Animation Timeline Audio Synchronization

We decided to synchronize custom vehicle audio via animation timeline sound events in `monster_truck.animation.json` registered through `sounds.json` and `sound_definitions.json`, rather than ambient entity mob sounds. This ties engine rev and idle loops directly to `query.modified_move_speed` state transitions in the animation controller, ensuring zero lag between driver throttle input and engine audio.

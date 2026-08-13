class_name GameConstants
extends Object

## Shared numbers for a scalable 2D action-roguelike.
## Keep gameplay feel here — rooms/enemies read these instead of magic numbers.

# Display / pixel grid (art drawn 1× then ×PX nearest)
const PX_SCALE := 2
const VIEW_W := 1280.0
const VIEW_H := 720.0

# World
const GROUND_Y := 620.0
const GROUND_H := 120.0
const TILE := 32.0

# Player locomotion (tuned so mid platforms are reachable)
const GRAVITY := 1600.0
const JUMP_V := -640.0  # apex ≈ 128px
const MOVE_SPEED := 240.0
const COYOTE_TIME := 0.12
const JUMP_BUFFER := 0.14

# Platform ladder (from ground up)
const PLAT_Y_LOW := 520.0
const PLAT_Y_MID := 420.0
const PLAT_Y_HIGH := 330.0
const PLAT_THICKNESS := 18.0
const PLAT_TEX_W := 96.0
const PLAT_TEX_H := 28.0

# Physics layers (match project.godot)
const LAYER_WORLD := 1
const LAYER_PLAYER := 2
const LAYER_ENEMY := 4
const LAYER_PLAYER_BULLET := 8
const LAYER_ENEMY_BULLET := 16

# Z draw order inside World
const Z_DECOR_BACK := -2
const Z_DECOR_FRONT := 2
const Z_PLATFORMS := 0
const Z_ENTITIES := 5
const Z_PROJECTILES := 8

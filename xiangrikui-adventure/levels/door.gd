extends Area2D

## Exit portal — pulses so players notice it after a clear.

@onready var sprite: Sprite2D = $Sprite

var _t: float = 0.0
var _base_y: float = 0.0


func _ready() -> void:
	collision_layer = 0
	collision_mask = GameConstants.LAYER_PLAYER
	monitoring = true
	monitorable = false
	z_index = GameConstants.Z_ENTITIES + 1
	_base_y = position.y
	scale = Vector2(0.4, 0.4)
	modulate = Color(1.4, 1.35, 0.8, 1.0)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(self, "modulate", Color.WHITE, 0.4)


func _process(delta: float) -> void:
	_t += delta
	if sprite:
		sprite.position.y = -72.0 + sin(_t * 3.2) * 4.0
		sprite.modulate = Color(1.0 + sin(_t * 4.0) * 0.15, 1.0 + sin(_t * 4.0) * 0.1, 0.85, 1.0)
	rotation = sin(_t * 1.6) * 0.03

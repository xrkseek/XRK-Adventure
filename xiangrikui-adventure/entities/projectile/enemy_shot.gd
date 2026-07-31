extends Area2D

var velocity: Vector2 = Vector2.ZERO
var damage: int = 1
var _life: float = 3.0
var fall_g: float = 0.0


func setup(vel: Vector2, dmg: int, g: float = 0.0) -> void:
	velocity = vel
	damage = dmg
	fall_g = g


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _physics_process(delta: float) -> void:
	velocity.y += fall_g * delta
	global_position += velocity * delta
	_life -= delta
	if _life <= 0.0:
		queue_free()


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player") and body.has_method("take_damage"):
		body.take_damage(damage)
		queue_free()

extends Area2D

var velocity: Vector2 = Vector2.ZERO
var damage: int = 1
var pierce: int = 0
var _life: float = 1.2
var _hit: Dictionary = {}


func setup(vel: Vector2, dmg: int, pierce_count: int) -> void:
	velocity = vel
	damage = dmg
	pierce = pierce_count


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	area_entered.connect(_on_area_entered)


func _physics_process(delta: float) -> void:
	global_position += velocity * delta
	_life -= delta
	if _life <= 0.0:
		queue_free()


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("enemy"):
		_hit_enemy(body)


func _on_area_entered(area: Node) -> void:
	if area.is_in_group("enemy_hurtbox"):
		var enemy := area.get_parent()
		if enemy:
			_hit_enemy(enemy)


func _hit_enemy(enemy: Node) -> void:
	if _hit.has(enemy):
		return
	_hit[enemy] = true
	if enemy.has_method("take_damage"):
		enemy.take_damage(damage)
	if pierce <= 0:
		queue_free()
	else:
		pierce -= 1

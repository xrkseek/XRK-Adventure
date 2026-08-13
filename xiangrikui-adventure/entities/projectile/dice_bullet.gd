extends Node2D

## 许月珍攻击弹：骰子。用 Node2D+_process，避免 Area2D 物理步进被关导致「看不见/不飞」。

var velocity: Vector2 = Vector2.ZERO
var damage: int = 1
var pierce: int = 0
var _life: float = 2.0
var _hit: Dictionary = {}

@onready var _area: Area2D = $Hit
@onready var _sprite: Sprite2D = $Sprite


func setup(vel: Vector2, dmg: int, pierce_count: int) -> void:
	velocity = vel
	damage = dmg
	pierce = pierce_count


func _ready() -> void:
	z_as_relative = false
	z_index = 30
	if _sprite:
		if _sprite.texture == null:
			_sprite.texture = load("res://assets/props/dice.png")
		_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	if _area:
		_area.monitoring = true
		_area.collision_layer = GameConstants.LAYER_PLAYER_BULLET
		_area.collision_mask = GameConstants.LAYER_ENEMY
		_area.body_entered.connect(_on_body_entered)
		_area.area_entered.connect(_on_area_entered)


func _process(delta: float) -> void:
	global_position += velocity * delta
	rotation += 12.0 * delta
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

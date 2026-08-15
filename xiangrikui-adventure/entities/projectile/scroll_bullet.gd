extends Node2D

## 王美嘉卷轴弹：短飞 → 空中悬浮旋转；旋转期间半径内敌人持续受伤。

var velocity: Vector2 = Vector2.ZERO
var damage: int = 1
var pierce: int = 0  # 保留接口；悬浮期用 tick，不靠穿透消弹
var size_scale: float = 1.0

const FLY_SPEED := 280.0
const MAX_RANGE := 170.0
const HOVER_TIME := 1.35
const SPIN_FLY := 10.0
const SPIN_HOVER := 16.0
const AOE_RADIUS := 52.0
const TICK_INTERVAL := 0.18

var _phase: String = "fly"  # fly | hover
var _traveled: float = 0.0
var _hover_left: float = HOVER_TIME
var _tick_cd: float = 0.0
var _hit_cd: Dictionary = {}  # enemy -> remaining cooldown
var _max_range: float = MAX_RANGE
var _aoe_radius: float = AOE_RADIUS

@onready var _area: Area2D = $Hit
@onready var _sprite: Sprite2D = $Sprite
@onready var _shape: CollisionShape2D = $Hit/CollisionShape2D


func setup(vel: Vector2, dmg: int, pierce_count: int, scale_mul: float = 1.0) -> void:
	# 短射程：压低传入速度，保留方向
	var dir := vel.normalized() if vel.length_squared() > 0.001 else Vector2.RIGHT
	size_scale = maxf(0.5, scale_mul)
	velocity = dir * (FLY_SPEED * size_scale)
	damage = dmg
	pierce = pierce_count
	_max_range = MAX_RANGE * size_scale
	_aoe_radius = AOE_RADIUS * size_scale


func _ready() -> void:
	z_as_relative = false
	z_index = 30
	if _sprite:
		if _sprite.texture == null:
			_sprite.texture = load("res://assets/props/scroll.png")
		_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_sprite.scale = Vector2.ONE * size_scale
	if _area:
		_area.monitoring = true
		_area.collision_layer = GameConstants.LAYER_PLAYER_BULLET
		_area.collision_mask = GameConstants.LAYER_ENEMY
		_area.body_entered.connect(_on_body_entered)
		_area.area_entered.connect(_on_area_entered)
	_set_hit_radius(16.0 * size_scale)


func _set_hit_radius(r: float) -> void:
	if _shape and _shape.shape is CircleShape2D:
		(_shape.shape as CircleShape2D).radius = r


func _process(delta: float) -> void:
	# 冷却表衰减
	var keys := _hit_cd.keys()
	for k in keys:
		_hit_cd[k] = float(_hit_cd[k]) - delta
		if float(_hit_cd[k]) <= 0.0:
			_hit_cd.erase(k)

	if _phase == "fly":
		var step := velocity * delta
		global_position += step
		_traveled += step.length()
		rotation += SPIN_FLY * delta
		if _traveled >= _max_range:
			_enter_hover()
	else:
		rotation += SPIN_HOVER * delta
		_hover_left -= delta
		_tick_cd = maxf(0.0, _tick_cd - delta)
		if _tick_cd <= 0.0:
			_tick_cd = TICK_INTERVAL
			_aoe_tick()
		if _hover_left <= 0.0:
			queue_free()


func _enter_hover() -> void:
	_phase = "hover"
	velocity = Vector2.ZERO
	_set_hit_radius(_aoe_radius)
	_aoe_tick()


func _aoe_tick() -> void:
	var tree := get_tree()
	if tree == null:
		return
	for enemy in tree.get_nodes_in_group("enemy"):
		if not (enemy is Node2D):
			continue
		var n2 := enemy as Node2D
		if global_position.distance_to(n2.global_position) <= _aoe_radius:
			_damage_enemy(enemy, false)


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("enemy"):
		# 飞行段首碰也伤一下；悬浮段交给 tick
		_damage_enemy(body, _phase == "fly")


func _on_area_entered(area: Node) -> void:
	if area.is_in_group("enemy_hurtbox"):
		var enemy := area.get_parent()
		if enemy:
			_damage_enemy(enemy, _phase == "fly")


func _damage_enemy(enemy: Node, destroy_on_hit: bool) -> void:
	if _hit_cd.has(enemy):
		return
	_hit_cd[enemy] = TICK_INTERVAL
	if enemy.has_method("take_damage"):
		enemy.take_damage(damage)
	if destroy_on_hit and pierce <= 0 and _phase == "fly":
		# 飞行撞到先进入悬浮，而不是立刻消失（卷轴「钉」在空中转）
		_enter_hover()
	elif destroy_on_hit and pierce > 0:
		pierce -= 1

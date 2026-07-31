class_name Enemy
extends CharacterBody2D

signal died

enum Kind { BUG, WEED, FLYER, BOSS }

@export var kind: Kind = Kind.BUG

@onready var sprite: Sprite2D = %Sprite
@onready var anim: AnimatedSprite2D = %Anim
@onready var hp_bar: ProgressBar = %HpBar

var hp: int = 2
var max_hp: int = 2
var damage: int = 1
var _flash: float = 0.0
var _shoot_cd: float = 1.0
var _dir: float = 1.0
var _base_y: float = 0.0
var _phase: float = 0.0
var _bound_left: float = 80.0
var _bound_right: float = 1000.0
var _dead: bool = false
var _contact_cd: float = 0.0

var shot_scene: PackedScene = preload("res://entities/projectile/enemy_shot.tscn")


func setup(enemy_kind: Kind, scale_factor: float = 1.0, room_w: float = 1200.0) -> void:
	kind = enemy_kind
	_bound_left = 80.0
	_bound_right = maxf(200.0, room_w - 80.0)
	match kind:
		Kind.BUG:
			hp = maxi(2, int(2.0 * scale_factor))
			damage = 1
		Kind.WEED:
			hp = maxi(3, int(3.0 * scale_factor))
			damage = 1
		Kind.FLYER:
			hp = maxi(2, int(2.0 * scale_factor))
			damage = 1
		Kind.BOSS:
			hp = maxi(28, int(28.0 + scale_factor * 8.0))
			damage = 2
	max_hp = hp
	add_to_group("enemy")


func _ready() -> void:
	_base_y = global_position.y
	_dir = -1.0 if RunManager.rng.randf() < 0.5 else 1.0
	_apply_visual()
	if hp_bar:
		hp_bar.max_value = max_hp
		hp_bar.value = hp
		hp_bar.visible = false


func _apply_visual() -> void:
	match kind:
		Kind.BUG:
			sprite.texture = load("res://assets/sprites/enemy_bug.png")
			sprite.visible = true
			anim.visible = false
		Kind.WEED:
			sprite.texture = load("res://assets/sprites/enemy_weed.png")
			sprite.visible = true
			anim.visible = false
		Kind.FLYER:
			sprite.visible = false
			anim.visible = true
			anim.sprite_frames = SpriteFactory.make_flyer_frames()
			anim.play("fly")
		Kind.BOSS:
			sprite.texture = load("res://assets/sprites/enemy_boss.png")
			sprite.visible = true
			anim.visible = false
			scale = Vector2(1.15, 1.15)


func _physics_process(delta: float) -> void:
	if _dead:
		return
	_flash = maxf(0.0, _flash - delta)
	_contact_cd = maxf(0.0, _contact_cd - delta)
	modulate = Color(2, 2, 2) if _flash > 0.0 else Color.WHITE
	_phase += delta

	var player := get_tree().get_first_node_in_group("player")
	if player and player.has_method("take_damage") and _contact_cd <= 0.0:
		if global_position.distance_to(player.global_position) < 36.0:
			player.take_damage(damage)
			_contact_cd = 0.35

	match kind:
		Kind.BUG:
			velocity.x = _dir * 80.0
			velocity.y += 1400.0 * delta
			move_and_slide()
			if is_on_wall() or not _floor_ahead():
				_dir *= -1.0
			sprite.flip_h = _dir > 0.0
		Kind.WEED:
			velocity = Vector2.ZERO
			_shoot_cd -= delta
			if _shoot_cd <= 0.0:
				_shoot_cd = 1.8
				_shoot_at_player(220.0)
		Kind.FLYER:
			global_position.x += _dir * 90.0 * delta
			global_position.y = _base_y + sin(_phase * 2.2) * 28.0
			if global_position.x < _bound_left or global_position.x > _bound_right:
				_dir *= -1.0
				global_position.x = clampf(global_position.x, _bound_left, _bound_right)
			anim.flip_h = _dir > 0.0
			_shoot_cd -= delta
			if _shoot_cd <= 0.0:
				_shoot_cd = 1.6
				_shoot_at_player(180.0)
		Kind.BOSS:
			velocity.x = _dir * 50.0
			move_and_slide()
			if is_on_wall():
				_dir *= -1.0
			_shoot_cd -= delta
			if _shoot_cd <= 0.0:
				_shoot_cd = 0.35 if hp < max_hp * 0.4 else 0.7
				_boss_ring()


func _floor_ahead() -> bool:
	var space := get_world_2d().direct_space_state
	var from := global_position + Vector2(_dir * 20.0, 8.0)
	var to := from + Vector2(0, 40)
	var q := PhysicsRayQueryParameters2D.create(from, to)
	q.collision_mask = 1
	return space.intersect_ray(q) != null


func _spawn_shot(vel: Vector2, dmg: int) -> void:
	var shot := shot_scene.instantiate()
	shot.global_position = global_position
	shot.setup(vel, dmg)
	var scene := get_tree().current_scene
	if scene and scene.has_method("spawn_projectile"):
		scene.spawn_projectile(shot)
	else:
		scene.add_child(shot)


func _shoot_at_player(speed: float) -> void:
	var player := get_tree().get_first_node_in_group("player")
	if player == null:
		return
	var dir: Vector2 = (player.global_position - global_position).normalized()
	_spawn_shot(dir * speed, damage)


func _boss_ring() -> void:
	for i in 5:
		var ang := (float(i) / 5.0) * TAU + _phase
		_spawn_shot(Vector2.from_angle(ang) * 160.0, damage)


func take_damage(amount: int) -> void:
	if _dead:
		return
	hp -= amount
	_flash = 0.12
	if hp_bar:
		hp_bar.visible = true
		hp_bar.value = hp
	if hp <= 0:
		_dead = true
		hp = 0
		RunManager.on_enemy_killed()
		died.emit()
		queue_free()

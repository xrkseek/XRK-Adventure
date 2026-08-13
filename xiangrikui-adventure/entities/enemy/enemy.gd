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
var _room_w: float = 1200.0
var _dead: bool = false
var _contact_cd: float = 0.0
var _stats_ready: bool = false

var shot_scene: PackedScene = preload("res://entities/projectile/enemy_shot.tscn")


func setup(enemy_kind: Kind, scale_factor: float = 1.0, room_w: float = 1200.0) -> void:
	kind = enemy_kind
	_room_w = room_w
	_bound_left = 64.0
	_bound_right = maxf(160.0, room_w - 64.0)
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
	_stats_ready = true
	add_to_group("enemy")
	if is_inside_tree():
		_capture_spawn_pose()
		_apply_visual()
		_sync_hp_bar()


func bind_spawn(spawn_pos: Vector2) -> void:
	## Call after add_child so global_position / _base_y are correct.
	global_position = spawn_pos
	_capture_spawn_pose()


func _capture_spawn_pose() -> void:
	if kind == Kind.FLYER:
		_base_y = clampf(global_position.y, 160.0, GameConstants.GROUND_Y - 100.0)
		global_position.y = _base_y
	else:
		# Ground units plant on the soil line (not midair / under map).
		global_position.y = GameConstants.GROUND_Y
		_base_y = GameConstants.GROUND_Y
	global_position.x = clampf(global_position.x, _bound_left, _bound_right)


func _ready() -> void:
	_dir = -1.0 if RunManager.rng.randf() < 0.5 else 1.0
	_capture_spawn_pose()
	_apply_visual()
	_sync_hp_bar()
	z_index = GameConstants.Z_ENTITIES
	if kind == Kind.FLYER:
		anim.z_index = 2
		modulate = Color(1.05, 1.05, 1.1, 1.0)


func _sync_hp_bar() -> void:
	if hp_bar == null:
		return
	hp_bar.max_value = max_hp
	hp_bar.value = hp
	hp_bar.visible = false


func _apply_visual() -> void:
	if anim == null or sprite == null:
		return
	sprite.visible = false
	anim.visible = true
	anim.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	match kind:
		Kind.BUG:
			anim.sprite_frames = SpriteFactory.make_bug_frames()
			anim.play("walk")
			anim.position = Vector2(0, -SpriteFactory.BUG_H * 0.5)
		Kind.WEED:
			anim.sprite_frames = SpriteFactory.make_weed_frames()
			anim.play("idle")
			anim.position = Vector2(0, -SpriteFactory.WEED_H * 0.5)
		Kind.FLYER:
			anim.sprite_frames = SpriteFactory.make_flyer_frames()
			anim.play("fly")
			anim.position = Vector2(0, -SpriteFactory.FLYER_H * 0.35)
		Kind.BOSS:
			anim.sprite_frames = SpriteFactory.make_boss_frames()
			anim.play("idle")
			anim.position = Vector2(0, -SpriteFactory.BOSS_H * 0.5)
			scale = Vector2.ONE


func _physics_process(delta: float) -> void:
	if _dead:
		return
	_flash = maxf(0.0, _flash - delta)
	_contact_cd = maxf(0.0, _contact_cd - delta)
	modulate = Color(2, 2, 2) if _flash > 0.0 else (
		Color(1.05, 1.05, 1.1, 1.0) if kind == Kind.FLYER else Color.WHITE
	)
	_phase += delta

	var player := get_tree().get_first_node_in_group("player")
	if player and player.has_method("take_damage") and _contact_cd <= 0.0:
		var hit_r := 48.0 if kind == Kind.FLYER else 36.0
		if global_position.distance_to(player.global_position) < hit_r:
			player.take_damage(damage)
			_contact_cd = 0.35

	match kind:
		Kind.BUG:
			_patrol_ground(delta, 80.0)
		Kind.WEED:
			velocity = Vector2.ZERO
			global_position.y = GameConstants.GROUND_Y
			global_position.x = clampf(global_position.x, _bound_left, _bound_right)
			_shoot_cd -= delta
			if _shoot_cd <= 0.0:
				_shoot_cd = 1.8
				_shoot_at_player(220.0)
		Kind.FLYER:
			_patrol_air(delta)
		Kind.BOSS:
			_patrol_ground(delta, 50.0)
			_shoot_cd -= delta
			if _shoot_cd <= 0.0:
				_shoot_cd = 0.35 if hp < max_hp * 0.4 else 0.7
				_boss_ring()

	_enforce_bounds()


func _patrol_ground(delta: float, speed: float) -> void:
	velocity.x = _dir * speed
	velocity.y += GameConstants.GRAVITY * delta
	move_and_slide()
	# Edge of room or missing floor ahead → turn (boss included).
	var at_edge := global_position.x <= _bound_left + 4.0 or global_position.x >= _bound_right - 4.0
	if is_on_wall() or at_edge or not _floor_ahead():
		_dir *= -1.0
		global_position.x = clampf(global_position.x, _bound_left, _bound_right)
	# Never sink under the soil line.
	if global_position.y > GameConstants.GROUND_Y:
		global_position.y = GameConstants.GROUND_Y
		velocity.y = minf(velocity.y, 0.0)
	anim.flip_h = _dir > 0.0


func _patrol_air(delta: float) -> void:
	global_position.x += _dir * 90.0 * delta
	global_position.y = _base_y + sin(_phase * 2.2) * 22.0
	if global_position.x <= _bound_left or global_position.x >= _bound_right:
		_dir *= -1.0
		global_position.x = clampf(global_position.x, _bound_left, _bound_right)
	anim.flip_h = _dir > 0.0
	_shoot_cd -= delta
	if _shoot_cd <= 0.0:
		_shoot_cd = 1.6
		_shoot_at_player(180.0)


func _enforce_bounds() -> void:
	## Out-of-map units must despawn or room clear / door never fires.
	global_position.x = clampf(global_position.x, _bound_left - 8.0, _bound_right + 8.0)
	if kind == Kind.FLYER:
		global_position.y = clampf(global_position.y, 120.0, GameConstants.GROUND_Y - 64.0)
		return
	if global_position.y > GameConstants.VIEW_H + 40.0:
		_despawn_out_of_bounds()


func _despawn_out_of_bounds() -> void:
	if _dead:
		return
	_dead = true
	remove_from_group("enemy")
	died.emit()
	queue_free()


func _floor_ahead() -> bool:
	var space := get_world_2d().direct_space_state
	if space == null:
		return true
	var from := global_position + Vector2(_dir * 24.0, 4.0)
	var to := from + Vector2(0, 48)
	var q := PhysicsRayQueryParameters2D.create(from, to)
	q.collision_mask = GameConstants.LAYER_WORLD
	q.exclude = [get_rid()]
	return space.intersect_ray(q) != null


func _spawn_shot(vel: Vector2, dmg: int) -> void:
	var shot := shot_scene.instantiate()
	shot.global_position = global_position + Vector2(0, -20)
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
		remove_from_group("enemy")
		RunManager.on_enemy_killed()
		died.emit()
		queue_free()

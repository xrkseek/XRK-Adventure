extends CharacterBody2D

signal died
signal health_changed(hp: int, max_hp: int)

@onready var anim: AnimatedSprite2D = %Anim
@onready var muzzle: Marker2D = %Muzzle
@onready var hurtbox: Area2D = %Hurtbox

const GRAVITY := GameConstants.GRAVITY
const COYOTE_TIME := GameConstants.COYOTE_TIME
const JUMP_BUFFER := GameConstants.JUMP_BUFFER
const DICE := preload("res://entities/projectile/dice_bullet.tscn")

var hp: int = 5
var max_hp: int = 5
var move_speed: float = GameConstants.MOVE_SPEED
var jump_v: float = GameConstants.JUMP_V
var fire_cd_max: float = 0.22
var damage: int = 1
var spread: int = 1
var pierce: int = 0

var _fire_cd: float = 0.0
var _coyote: float = 0.0
var _jump_buf: float = 0.0
var _invuln: float = 0.0
var _facing: float = 1.0
var _can_control: bool = true
var _dead: bool = false
var _attack_lock: float = 0.0
var _bound_left: float = 28.0
var _bound_right: float = 1250.0


func bind_room(room_w: float) -> void:
	_bound_left = 28.0
	_bound_right = maxf(120.0, room_w - 28.0)
	global_position.x = clampf(global_position.x, _bound_left, _bound_right)


func _ready() -> void:
	anim.sprite_frames = SpriteFactory.make_character_frames()
	var cell := SpriteFactory.player_cell_size()
	anim.position = Vector2(0, -cell.y * 0.5)
	anim.play("idle")
	_sync_from_run()
	health_changed.emit(hp, max_hp)


func _sync_from_run() -> void:
	var s: Dictionary = RunManager.player_stats
	hp = int(s["hp"])
	max_hp = int(s["max_hp"])
	move_speed = float(s["speed"])
	jump_v = float(s["jump_v"])
	fire_cd_max = float(s["fire_cd"])
	damage = int(s["damage"])
	spread = int(s["spread"])
	pierce = int(s["pierce"])


func enable_control(enabled: bool) -> void:
	_can_control = enabled
	if not enabled:
		velocity.x = 0.0


func _physics_process(delta: float) -> void:
	if _invuln > 0.0:
		_invuln -= delta
		anim.modulate.a = 0.4 if int(_invuln * 12.0) % 2 == 0 else 1.0
	else:
		anim.modulate.a = 1.0

	_fire_cd = maxf(0.0, _fire_cd - delta)

	if not _can_control or _dead:
		if not is_on_floor():
			velocity.y += GRAVITY * delta
		move_and_slide()
		_enforce_room_bounds()
		return

	var input_x := Input.get_axis("move_left", "move_right")
	if input_x != 0.0:
		_facing = signf(input_x)
		anim.flip_h = _facing < 0.0

	if is_on_floor():
		velocity.x = input_x * move_speed
		_coyote = COYOTE_TIME
	else:
		velocity.x = move_toward(velocity.x, input_x * move_speed, 1400.0 * delta)
		_coyote = maxf(0.0, _coyote - delta)

	if not is_on_floor():
		velocity.y += GRAVITY * delta
	elif velocity.y > 0.0:
		velocity.y = 0.0

	if Input.is_action_just_pressed("jump"):
		_jump_buf = JUMP_BUFFER
	_jump_buf = maxf(0.0, _jump_buf - delta)

	if _jump_buf > 0.0 and _coyote > 0.0:
		velocity.y = jump_v
		_coyote = 0.0
		_jump_buf = 0.0

	if Input.is_action_just_released("jump") and velocity.y < -120.0:
		velocity.y *= 0.55

	move_and_slide()
	_enforce_room_bounds()
	if _attack_lock > 0.0:
		_attack_lock = maxf(0.0, _attack_lock - delta)
	_update_anim()

	if _wants_shoot():
		fire_at_aim()


func _wants_shoot() -> bool:
	if Input.is_action_pressed("shoot"):
		return true
	# 右扳机强度有时不进 action
	return Input.get_joy_axis(0, JOY_AXIS_TRIGGER_RIGHT) > 0.35


func _aim_direction() -> Vector2:
	var stick := Input.get_vector("aim_left", "aim_right", "aim_up", "aim_down")
	if stick.length() >= 0.35:
		return stick.normalized()
	if Settings != null and Settings.want_touch_controls():
		return Vector2(_facing, 0.0)
	var to_mouse := get_global_mouse_position() - _muzzle_global()
	if to_mouse.length_squared() >= 36.0:
		return to_mouse.normalized()
	return Vector2(_facing, 0.0)


func _enforce_room_bounds() -> void:
	## Keep feet on stage: side clamp + soft recover if somehow falling past the floor.
	global_position.x = clampf(global_position.x, _bound_left, _bound_right)
	if global_position.y < 48.0:
		global_position.y = 48.0
		if velocity.y < 0.0:
			velocity.y = 0.0
	if global_position.y > GameConstants.VIEW_H + 40.0:
		global_position.x = clampf(global_position.x, _bound_left, _bound_right)
		global_position.y = GameConstants.GROUND_Y
		velocity = Vector2.ZERO


func _update_anim() -> void:
	if _attack_lock > 0.0:
		if anim.animation != &"attack":
			anim.play(&"attack")
		return
	if not is_on_floor():
		if anim.animation != &"jump":
			anim.play(&"jump")
	elif absf(velocity.x) > 12.0:
		if anim.animation != &"walk":
			anim.play(&"walk")
	else:
		if anim.animation != &"idle":
			anim.play(&"idle")


## 朝瞄准方向发射骰子（鼠标 / 右摇杆 / 面向）
func fire_at_aim() -> void:
	if _fire_cd > 0.0:
		return
	_fire_cd = fire_cd_max
	_attack_lock = 0.2

	var origin := _muzzle_global()
	var dir := _aim_direction()
	_facing = 1.0 if dir.x >= 0.0 else -1.0
	anim.flip_h = _facing < 0.0
	origin = _muzzle_global()

	var n := maxi(1, spread)
	var spread_ang := 0.18 if n > 1 else 0.0
	for i in n:
		var t := 0.0 if n == 1 else (float(i) / float(n - 1) - 0.5) * 2.0
		_spawn_dice(origin, Vector2.from_angle(dir.angle() + t * spread_ang) * 560.0)

	if anim.sprite_frames and anim.sprite_frames.has_animation(&"attack"):
		anim.play(&"attack")
	if Settings:
		Settings.pulse_vibrate(18)


## 兼容旧冒烟测试名
func fire_at_mouse() -> void:
	fire_at_aim()


func _muzzle_global() -> Vector2:
	var mx := absf(muzzle.position.x)
	return global_position + Vector2(-mx if anim.flip_h else mx, muzzle.position.y)


func _spawn_dice(origin: Vector2, vel: Vector2) -> void:
	var bucket := get_tree().get_first_node_in_group("projectiles")
	if bucket == null:
		bucket = get_parent()
	if bucket == null:
		push_error("No projectile bucket")
		return
	var bullet: Node2D = DICE.instantiate()
	bucket.add_child(bullet)
	bullet.global_position = origin
	bullet.call("setup", vel, damage, pierce)


func take_damage(amount: int) -> void:
	if _dead or hp <= 0:
		return
	if _invuln > 0.0:
		return
	hp -= amount
	_invuln = 1.0
	velocity.y = -220.0
	RunManager.player_stats["hp"] = hp
	health_changed.emit(hp, max_hp)
	RunManager.stats_changed.emit()
	if hp <= 0:
		hp = 0
		_dead = true
		_can_control = false
		velocity.x = 0.0
		died.emit()
		RunManager.on_player_died()


func heal_full_from_stats() -> void:
	_sync_from_run()
	health_changed.emit(hp, max_hp)

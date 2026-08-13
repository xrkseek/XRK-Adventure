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
	if _attack_lock > 0.0:
		_attack_lock = maxf(0.0, _attack_lock - delta)
	_update_anim()

	# 底层直读键鼠，不依赖 InputMap/UI 是否吞掉 shoot action
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or Input.is_physical_key_pressed(KEY_J):
		fire_at_mouse()


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


## 朝鼠标发射骰子（公开，便于冒烟测试）
func fire_at_mouse() -> void:
	if _fire_cd > 0.0:
		return
	_fire_cd = fire_cd_max
	_attack_lock = 0.2

	var origin := _muzzle_global()
	var aim := get_global_mouse_position() - origin
	var dir := aim.normalized() if aim.length_squared() >= 9.0 else Vector2(_facing, 0.0)
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

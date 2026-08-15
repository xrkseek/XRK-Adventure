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
const SCROLL := preload("res://entities/projectile/scroll_bullet.tscn")
const CHAIN := preload("res://entities/projectile/chain_slash.tscn")
const PROJECTILE_SPEED_DICE := 560.0
const PROJECTILE_SPEED_SCROLL := 280.0

var hp: int = 5
var max_hp: int = 5
var move_speed: float = GameConstants.MOVE_SPEED
var jump_v: float = GameConstants.JUMP_V
var fire_cd_max: float = 0.22
var damage: int = 1
var spread: int = 1
var pierce: int = 0
var proj_scale: float = 1.0
var reach_mul: float = 1.0
var invuln_bonus: float = 0.0

var _fire_cd: float = 0.0
var _coyote: float = 0.0
var _jump_buf: float = 0.0
var _invuln: float = 0.0
var _facing: float = 1.0
var _can_control: bool = true
var _dead: bool = false
var _attack_lock: float = 0.0
var _land_lock: float = 0.0
var _was_on_floor: bool = true
var _jump_ascent: Array = [0, 1, 2]
var _jump_peak: int = 3
var _jump_descent: Array = [4, 5]
var _jump_land: Array = [6, 7]
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
	_sync_collision_from_texture()
	_cache_jump_phases()
	anim.play("idle")
	_sync_from_run()
	if not RunManager.stats_changed.is_connected(_sync_from_run):
		RunManager.stats_changed.connect(_sync_from_run)
	health_changed.emit(hp, max_hp)


func _sync_collision_from_texture() -> void:
	## 碰撞 = idle 贴图不透明 bbox（不手写宽高）。debug 蓝框会跟着贴图走。
	if anim == null or anim.sprite_frames == null:
		return
	if not anim.sprite_frames.has_animation(&"idle"):
		return
	var tex: Texture2D = anim.sprite_frames.get_frame_texture(&"idle", 0)
	var opaque := _texture_opaque_rect(tex)
	if opaque.size.x < 2 or opaque.size.y < 2:
		return
	var cell := SpriteFactory.player_cell_size()
	# Anim 中心在 anim.position；贴图左上相对角色脚底原点：
	var sprite_top_left := anim.position - Vector2(cell) * 0.5
	var size := Vector2(opaque.size)
	var center := sprite_top_left + Vector2(opaque.position) + size * 0.5
	var body := get_node_or_null("CollisionShape2D") as CollisionShape2D
	if body and body.shape is RectangleShape2D:
		(body.shape as RectangleShape2D).size = size
		body.position = center
	if hurtbox:
		var hs := hurtbox.get_node_or_null("HurtShape") as CollisionShape2D
		if hs:
			hs.position = center
	if muzzle:
		# 贴图中上部偏右（出手点），不手写魔法数 cell
		muzzle.position = Vector2(center.x + size.x * 0.25, sprite_top_left.y + float(opaque.position.y) + size.y * 0.35)


func _texture_opaque_rect(tex: Texture2D) -> Rect2i:
	if tex == null:
		return Rect2i()
	var img: Image = null
	var offset := Vector2i.ZERO
	if tex is AtlasTexture:
		var at := tex as AtlasTexture
		if at.atlas == null:
			return Rect2i()
		img = at.atlas.get_image()
		if img == null:
			return Rect2i()
		var r := at.region
		img = img.get_region(Rect2i(int(r.position.x), int(r.position.y), int(r.size.x), int(r.size.y)))
	else:
		img = tex.get_image()
	if img == null:
		return Rect2i()
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	return img.get_used_rect()


func _cache_jump_phases() -> void:
	var profile := SpriteFactory.load_character_profile()
	var st: Dictionary = profile.get("states", {}).get("jump", {})
	var phases: Dictionary = st.get("phases", {})
	_jump_ascent = phases.get("ascent", [0, 1, 2])
	_jump_peak = int(phases.get("peak", 3))
	_jump_descent = phases.get("descent", [4, 5])
	_jump_land = phases.get("land", [6, 7])
	var fc := 3
	if anim.sprite_frames and anim.sprite_frames.has_animation(&"jump"):
		fc = anim.sprite_frames.get_frame_count(&"jump")
	# 旧 3 帧 sheet：ascent[0] peak[1] land[2]
	if fc <= 3:
		_jump_ascent = [0]
		_jump_peak = mini(1, fc - 1)
		_jump_descent = [mini(1, fc - 1)]
		_jump_land = [maxi(0, fc - 1)]


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
	proj_scale = float(s.get("proj_scale", 1.0))
	reach_mul = float(s.get("reach_mul", 1.0))
	invuln_bonus = float(s.get("invuln_bonus", 0.0))
	health_changed.emit(hp, max_hp)


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
	if _land_lock > 0.0:
		_land_lock = maxf(0.0, _land_lock - delta)
	_update_anim()
	_was_on_floor = is_on_floor()

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
		var cur := String(anim.animation)
		if not (cur == "attack" or cur.begins_with("attack_")):
			if anim.sprite_frames and anim.sprite_frames.has_animation(&"attack"):
				anim.play(&"attack")
		return
	var on_floor := is_on_floor()
	# 刚落地：播 land 帧短锁
	if on_floor and not _was_on_floor and _jump_land.size() > 0:
		_land_lock = 0.18
		if anim.animation != &"jump":
			anim.play(&"jump")
		anim.frame = int(_jump_land[0])
		anim.pause()
	if _land_lock > 0.0 and on_floor:
		_update_jump_land()
		return
	if not on_floor:
		_update_jump_air()
	elif absf(velocity.x) > 12.0:
		if anim.animation != &"walk":
			anim.play(&"walk")
	else:
		if anim.animation != &"idle":
			anim.play(&"idle")


func _update_jump_air() -> void:
	## ascent → hold peak → descent（读 character.json states.jump.phases）
	if anim.animation != &"jump":
		anim.play(&"jump")
		if _jump_ascent.size() > 0:
			anim.frame = int(_jump_ascent[0])
		return
	var ascent_end := int(_jump_ascent[_jump_ascent.size() - 1]) if _jump_ascent.size() > 0 else 0
	var descent_start := int(_jump_descent[0]) if _jump_descent.size() > 0 else _jump_peak
	var descent_end := int(_jump_descent[_jump_descent.size() - 1]) if _jump_descent.size() > 0 else _jump_peak
	if velocity.y <= 0.0:
		# 上升：播完 ascent 停在 peak
		if anim.frame < ascent_end:
			anim.play(&"jump")
		else:
			anim.frame = _jump_peak
			anim.pause()
	else:
		# 下落：descent 帧
		if anim.frame < descent_start:
			anim.frame = descent_start
			anim.play(&"jump")
		elif anim.frame >= descent_end:
			anim.frame = descent_end
			anim.pause()
		else:
			anim.play(&"jump")


func _update_jump_land() -> void:
	if anim.animation != &"jump":
		anim.play(&"jump")
	var land0 := int(_jump_land[0])
	var land1 := int(_jump_land[_jump_land.size() - 1])
	if _land_lock > 0.09:
		anim.frame = land0
	else:
		anim.frame = land1
	anim.pause()


## 朝瞄准方向攻击；弹种/近战读 character.json
func fire_at_aim() -> void:
	if _fire_cd > 0.0:
		return
	var profile := SpriteFactory.load_character_profile()
	var mode := str(profile.get("attack_mode", "ranged"))
	var base_dmg := int(profile.get("base_damage", 0))
	var hit_dmg := maxi(damage, base_dmg) if base_dmg > 0 else damage

	_fire_cd = fire_cd_max
	if mode == "melee":
		_fire_cd = maxf(_fire_cd, float(profile.get("attack_duration", 0.3)) * 0.85)
		_attack_lock = float(profile.get("attack_duration", 0.3))
	else:
		_attack_lock = 0.2

	var origin := _muzzle_global()
	var dir := _aim_direction()
	if absf(dir.x) > 0.2:
		_facing = signf(dir.x)
	# 近战/远程都按瞄准翻面；纯上/下保持原朝向
	anim.flip_h = _facing < 0.0
	origin = _muzzle_aimed(dir)

	if mode == "melee":
		# 三叶齐射 → 扇形多段挥击；硕果累累 → 特效/碰撞放大
		var n := maxi(1, spread)
		var spread_ang := 0.28 if n > 1 else 0.0
		for i in n:
			var t := 0.0 if n == 1 else (float(i) / float(n - 1) - 0.5) * 2.0
			var slash_dir := Vector2.from_angle(dir.angle() + t * spread_ang)
			_spawn_melee_chain(origin, slash_dir, hit_dmg, profile)
	else:
		var kind := str(profile.get("projectile", "dice"))
		if kind.is_empty():
			kind = "dice"
		var speed := PROJECTILE_SPEED_SCROLL if kind == "scroll" else PROJECTILE_SPEED_DICE
		speed *= reach_mul
		var n := maxi(1, spread)
		var spread_ang := 0.18 if n > 1 else 0.0
		for i in n:
			var t := 0.0 if n == 1 else (float(i) / float(n - 1) - 0.5) * 2.0
			_spawn_projectile(origin, Vector2.from_angle(dir.angle() + t * spread_ang) * speed, kind, hit_dmg)

	_play_attack_anim(dir, profile)
	if Settings:
		Settings.pulse_vibrate(18)


## 兼容旧冒烟测试名
func fire_at_mouse() -> void:
	fire_at_aim()


func _muzzle_global() -> Vector2:
	var mx := absf(muzzle.position.x)
	return global_position + Vector2(-mx if anim.flip_h else mx, muzzle.position.y)


func _muzzle_aimed(dir: Vector2) -> Vector2:
	## 八向枪口：沿瞄准方向偏移，避免纯上/下时枪口还在左右
	var d := dir.normalized() if dir.length_squared() > 0.0001 else Vector2(_facing, 0.0)
	var reach := 28.0
	return global_position + Vector2(0, -36.0) + d * reach


func _play_attack_anim(dir: Vector2, profile: Dictionary) -> void:
	if anim.sprite_frames == null:
		return
	var name := SpriteFactory.attack_anim_name_for_aim(dir, profile)
	if anim.sprite_frames.has_animation(name):
		anim.flip_h = SpriteFactory.attack_anim_flip_h(dir, profile)
		anim.play(name)
	elif anim.sprite_frames.has_animation(&"attack"):
		anim.play(&"attack")


func _projectile_kind() -> String:
	var profile := SpriteFactory.load_character_profile()
	var kind := str(profile.get("projectile", "dice"))
	return kind if kind != "" else "dice"


func _spawn_melee_chain(origin: Vector2, aim_dir: Vector2, dmg: int, profile: Dictionary) -> void:
	var bucket := get_tree().get_first_node_in_group("projectiles")
	if bucket == null:
		bucket = get_parent()
	if bucket == null:
		push_error("No projectile bucket")
		return
	var slash: Node2D = CHAIN.instantiate()
	bucket.add_child(slash)
	slash.global_position = origin
	# pierce：近战加成到挥击距离
	var reach := float(profile.get("attack_reach", 110.0)) * reach_mul * (1.0 + 0.12 * float(pierce))
	slash.call(
		"setup",
		aim_dir,
		dmg,
		reach,
		float(profile.get("attack_duration", 0.3)),
		bool(profile.get("block_bullets", true)),
		proj_scale
	)


func _spawn_projectile(origin: Vector2, vel: Vector2, kind: String = "", dmg: int = -1) -> void:
	if kind.is_empty():
		kind = _projectile_kind()
	if dmg < 0:
		dmg = damage
	var bucket := get_tree().get_first_node_in_group("projectiles")
	if bucket == null:
		bucket = get_parent()
	if bucket == null:
		push_error("No projectile bucket")
		return
	var scene: PackedScene = SCROLL if kind == "scroll" else DICE
	var bullet: Node2D = scene.instantiate()
	bucket.add_child(bullet)
	bullet.global_position = origin
	bullet.call("setup", vel, dmg, pierce, proj_scale)


## 兼容旧名
func _spawn_dice(origin: Vector2, vel: Vector2) -> void:
	_spawn_projectile(origin, vel, "dice")


func take_damage(amount: int) -> void:
	if _dead or hp <= 0:
		return
	if _invuln > 0.0:
		return
	hp -= amount
	_invuln = 1.0 + invuln_bonus
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

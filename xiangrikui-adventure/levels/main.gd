extends Node2D

@onready var world: Node2D = %World
@onready var entities: Node2D = %Entities
@onready var platforms: Node2D = %Platforms
@onready var decor_back: Node2D = %DecorBack
@onready var decor_front: Node2D = %DecorFront
@onready var projectiles: Node2D = %Projectiles
@onready var camera: Camera2D = %Camera
@onready var bg: Sprite2D = %Bg
@onready var mid_bg: Sprite2D = %MidBg
@onready var clouds: Node2D = %Clouds
@onready var hud: CanvasLayer = %HUD
@onready var title_ui: Control = %TitleUI
@onready var upgrade_ui: Control = %UpgradeUI
@onready var end_ui: Control = %EndUI

var player: CharacterBody2D
var door: Area2D
var room_width: float = 1200.0
var _shake: float = 0.0
var _cleared: bool = false
var _room_gen: int = 0
var _title_petals: Array[Sprite2D] = []
var _on_title: bool = true
var _ambient_t: float = 0.0
var current_theme: RoomBuilder.RoomTheme = RoomBuilder.RoomTheme.MEADOW

var player_scene: PackedScene = preload("res://entities/player/player.tscn")
var enemy_scene: PackedScene = preload("res://entities/enemy/enemy.tscn")
var door_scene: PackedScene = preload("res://levels/door.tscn")


func _ready() -> void:
	RunManager.run_started.connect(_on_run_started)
	RunManager.run_ended.connect(_on_run_ended)
	RunManager.upgrade_offered.connect(_on_upgrade_offered)
	projectiles.add_to_group("projectiles")
	title_ui.visible = true
	upgrade_ui.visible = false
	end_ui.visible = false
	hud.visible = false
	entities.z_index = GameConstants.Z_ENTITIES
	projectiles.z_index = GameConstants.Z_PROJECTILES
	decor_back.z_index = GameConstants.Z_DECOR_BACK
	decor_front.z_index = GameConstants.Z_DECOR_FRONT
	_show_title_bg()
	var args := OS.get_cmdline_user_args()
	if "--smoke-title" in args:
		call_deferred("_smoke_title_start")
	elif "--smoke-shoot" in args:
		call_deferred("_smoke_shoot")


func _smoke_title_start() -> void:
	var ev := InputEventKey.new()
	ev.keycode = KEY_ENTER
	ev.physical_keycode = KEY_ENTER
	ev.pressed = true
	_input(ev)
	await get_tree().process_frame
	await get_tree().process_frame
	var ok := RunManager.mode == "play" and not title_ui.visible and player != null
	print("SMOKE_TITLE ok=", ok, " mode=", RunManager.mode, " title_vis=", title_ui.visible, " has_player=", player != null)
	get_tree().quit(0 if ok else 1)


func _smoke_shoot() -> void:
	RunManager.start_run()
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	if player == null or not is_instance_valid(player):
		print("SMOKE_SHOOT fail=no_player")
		get_tree().quit(1)
		return
	var before := projectiles.get_child_count()
	player.set("_fire_cd", 0.0)
	player.call("fire_at_mouse")
	await get_tree().process_frame
	var after := projectiles.get_child_count()
	print("SMOKE_SHOOT ok=", after > before, " before=", before, " after=", after)
	get_tree().quit(0 if after > before else 1)


func _input(event: InputEvent) -> void:
	if not _is_menu_mode():
		return
	if event.is_echo() or not event.is_pressed():
		return
	if _event_requests_start(event):
		RunManager.start_run()
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_shake = maxf(0.0, _shake - delta * 1.6)
	_ambient_t += delta
	_tick_title_petals(delta)
	_tick_ambient(delta)
	if clouds and not _on_title:
		for c in clouds.get_children():
			if c is Sprite2D:
				c.position.x += delta * float(c.get_meta("spd", 8.0))
				if c.position.x > room_width + 80.0:
					c.position.x = -80.0
				# gentle vertical bob
				var base_y := float(c.get_meta("base_y", c.position.y))
				if not c.has_meta("base_y"):
					c.set_meta("base_y", c.position.y)
					base_y = c.position.y
				c.position.y = base_y + sin(_ambient_t * 1.2 + c.position.x * 0.01) * 3.0
	if player and RunManager.mode == "play" and is_instance_valid(player):
		var target := Vector2(player.global_position.x, GameConstants.VIEW_H * 0.5)
		target.x = clampf(target.x, GameConstants.VIEW_W * 0.5, maxf(GameConstants.VIEW_W * 0.5, room_width - GameConstants.VIEW_W * 0.5))
		camera.global_position = camera.global_position.lerp(target, 1.0 - pow(0.001, delta))
		var trauma := _shake * _shake
		camera.offset = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * 14.0 * trauma
		if mid_bg and mid_bg.texture and mid_bg.visible:
			# Soft parallax only — mid is wider than the room so edges never open a void.
			var mid_base_y := float(mid_bg.get_meta("base_y", GameConstants.GROUND_Y - GameConstants.VIEW_H * 0.5))
			var mid_pad := float(mid_bg.get_meta("pad_x", 0.0))
			mid_bg.position.x = -mid_pad - camera.global_position.x * 0.06
			mid_bg.position.y = mid_base_y + sin(_ambient_t * 0.35) * 1.5


func _tick_ambient(_delta: float) -> void:
	if _on_title or RunManager.mode == "title":
		return
	for layer in [decor_back, decor_front, platforms]:
		if layer == null:
			continue
		_animate_ambient_node(layer)


func _animate_ambient_node(node: Node) -> void:
	for c in node.get_children():
		if c.get_child_count() > 0:
			_animate_ambient_node(c)
		if not (c is CanvasItem):
			continue
		if not c.has_meta("ambient"):
			continue
		var kind := String(c.get_meta("ambient"))
		var phase := float(c.get_meta("phase", 0.0))
		var amp := float(c.get_meta("amp", 0.04))
		var t := _ambient_t + phase
		match kind:
			"sway":
				c.rotation = sin(t * 1.7) * amp
			"bob":
				if not c.has_meta("bob0"):
					c.set_meta("bob0", c.position.y)
				c.position.y = float(c.get_meta("bob0")) + sin(t * 2.4) * 1.5
			"sway_bob":
				c.rotation = sin(t * 2.1) * amp
				if not c.has_meta("bob0"):
					c.set_meta("bob0", c.position.y)
				c.position.y = float(c.get_meta("bob0")) + sin(t * 2.8) * 2.0


func _tick_title_petals(delta: float) -> void:
	if not _on_title:
		return
	for p in _title_petals:
		if not is_instance_valid(p):
			continue
		p.position.y += delta * float(p.get_meta("fall", 28.0))
		p.position.x += sin(p.position.y * 0.04) * delta * 18.0
		p.rotation += delta * float(p.get_meta("spin", 1.0))
		if p.position.y > GameConstants.VIEW_H + 40.0:
			p.position = Vector2(randf_range(40, GameConstants.VIEW_W - 40), randf_range(-40, -10))


func _is_menu_mode() -> bool:
	return RunManager.mode == "title" or RunManager.mode == "dead" or RunManager.mode == "win"


func _event_requests_start(event: InputEvent) -> bool:
	if event.is_action("confirm") or event.is_action("ui_accept") or event.is_action("jump"):
		return true
	if RunManager.mode == "title" and event.is_action("shoot"):
		return true
	if (RunManager.mode == "dead" or RunManager.mode == "win") and event.is_action("restart"):
		return true
	if event is InputEventKey:
		var k := event as InputEventKey
		if (
			k.keycode == KEY_ENTER
			or k.keycode == KEY_KP_ENTER
			or k.physical_keycode == KEY_ENTER
			or k.physical_keycode == KEY_KP_ENTER
			or k.keycode == KEY_SPACE
			or k.physical_keycode == KEY_SPACE
		):
			return true
		if (RunManager.mode == "dead" or RunManager.mode == "win") and (
			k.keycode == KEY_R or k.physical_keycode == KEY_R
		):
			return true
	return false


func _show_title_bg() -> void:
	_on_title = true
	if has_node("TitleLayer"):
		$TitleLayer.visible = true
	title_ui.visible = true
	title_ui.mouse_filter = Control.MOUSE_FILTER_STOP
	bg.texture = load("res://assets/bg/title.png")
	bg.centered = false
	bg.position = Vector2.ZERO
	# title.png is 960x540 @2x from 480x270
	bg.scale = Vector2(GameConstants.VIEW_W / 960.0, GameConstants.VIEW_H / 540.0)
	if mid_bg:
		mid_bg.visible = false
	_spawn_title_petals()
	camera.global_position = Vector2(GameConstants.VIEW_W * 0.5, GameConstants.VIEW_H * 0.5)
	camera.offset = Vector2.ZERO
	camera.limit_top = 0
	camera.limit_bottom = int(GameConstants.VIEW_H)
	camera.make_current()


func _spawn_title_petals() -> void:
	for p in _title_petals:
		if is_instance_valid(p):
			p.queue_free()
	_title_petals.clear()
	var tex: Texture2D = load("res://assets/decor/petal.png")
	for i in 14:
		var s := Sprite2D.new()
		s.texture = tex
		s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		s.z_index = -5
		s.position = Vector2(randf_range(40, GameConstants.VIEW_W - 40), randf_range(-20, GameConstants.VIEW_H - 80))
		s.modulate = Color(1, 1, 1, randf_range(0.55, 0.95))
		s.scale = Vector2.ONE * randf_range(0.8, 1.4)
		s.set_meta("fall", randf_range(18.0, 42.0))
		s.set_meta("spin", randf_range(-1.6, 1.6))
		add_child(s)
		_title_petals.append(s)


func _clear_title_petals() -> void:
	for p in _title_petals:
		if is_instance_valid(p):
			p.queue_free()
	_title_petals.clear()


func _on_run_started() -> void:
	_on_title = false
	_clear_title_petals()
	if has_node("TitleLayer"):
		$TitleLayer.visible = false
	title_ui.visible = false
	end_ui.visible = false
	upgrade_ui.visible = false
	hud.visible = true
	get_viewport().gui_release_focus()
	_build_room()


func _on_run_ended(_victory: bool) -> void:
	if player and is_instance_valid(player):
		player.enable_control(false)
	_clear_projectiles()
	end_ui.visible = true
	end_ui.call("show_result", _victory, RunManager.floor_num, RunManager.kills, RunManager.upgrade_names)


func _on_upgrade_offered(choices: Array) -> void:
	if player and is_instance_valid(player):
		player.enable_control(false)
	_clear_projectiles()
	upgrade_ui.visible = true
	upgrade_ui.call("show_choices", choices)


func on_upgrade_picked(upgrade: Dictionary) -> void:
	if RunManager.mode != "upgrade":
		return
	upgrade_ui.visible = false
	get_viewport().gui_release_focus()
	RunManager.apply_upgrade(upgrade)
	if RunManager.mode == "play":
		_build_room()


func _clear_layer(node: Node) -> void:
	if node == null:
		return
	for c in node.get_children():
		c.queue_free()


func _build_room() -> void:
	_room_gen += 1
	_cleared = false
	_clear_layer(entities)
	_clear_projectiles()
	door = null
	player = null

	var floor_n := RunManager.floor_num
	var is_boss := floor_n >= RunManager.MAX_FLOOR and RunManager.room_num == RunManager.ROOMS_PER_FLOOR - 1
	current_theme = RoomBuilder.pick_theme(floor_n, RunManager.room_num, is_boss)
	room_width = 1280.0 + floor_n * 80.0

	_on_title = false
	_clear_title_petals()
	# Cover full room (+ pad). Never leave a blue void on the right when scrolling.
	var cover_w := maxf(room_width, GameConstants.VIEW_W) + 160.0
	bg.texture = load(RoomBuilder.sky_path(current_theme))
	bg.centered = false
	bg.position = Vector2(-40, 0)
	var sky_tw := float(bg.texture.get_width())
	var sky_th := float(bg.texture.get_height())
	bg.scale = Vector2(cover_w / sky_tw, GameConstants.VIEW_H / sky_th)
	if mid_bg:
		mid_bg.texture = load("res://assets/bg/mid.png")
		mid_bg.visible = current_theme != RoomBuilder.RoomTheme.CREEK
		mid_bg.centered = false
		var mid_tw := float(mid_bg.texture.get_width())
		var mid_th := float(mid_bg.texture.get_height())
		# Hills should read tall (not a flat ribbon): ~55% of view, foot at GROUND_Y.
		var mid_screen_h := GameConstants.VIEW_H * 0.55
		var mid_cover := cover_w * 1.15
		mid_bg.scale = Vector2(mid_cover / mid_tw, mid_screen_h / mid_th)
		var mid_base_y := GameConstants.GROUND_Y - mid_screen_h
		var mid_pad := 80.0
		mid_bg.set_meta("base_y", mid_base_y)
		mid_bg.set_meta("pad_x", mid_pad)
		mid_bg.position = Vector2(-mid_pad, mid_base_y)
		mid_bg.modulate = Color(1, 0.9, 0.85, 0.92) if current_theme == RoomBuilder.RoomTheme.DUSK else Color(1, 1, 1, 1.0)

	var builder := RoomBuilder.new(RunManager.rng)
	builder.build(platforms, decor_back, decor_front, clouds, room_width, floor_n, current_theme)

	player = player_scene.instantiate()
	player.add_to_group("player")
	player.global_position = Vector2(110, GameConstants.GROUND_Y)
	entities.add_child(player)
	player.died.connect(_on_player_died)
	player.heal_full_from_stats()
	player.enable_control(true)
	camera.global_position = Vector2(GameConstants.VIEW_W * 0.5, GameConstants.VIEW_H * 0.5)
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = int(room_width)
	camera.limit_bottom = int(GameConstants.VIEW_H)
	camera.make_current()

	var scale_f := 1.0 + (floor_n - 1) * 0.12
	if is_boss:
		_spawn_enemy(Enemy.Kind.BOSS, Vector2(room_width * 0.55, GameConstants.GROUND_Y), scale_f)
	else:
		_spawn_theme_enemies(floor_n, scale_f)

	hud.call("refresh", RoomBuilder.theme_name(current_theme))


func _spawn_theme_enemies(floor_n: int, scale_f: float) -> void:
	var count := 3 + floor_n
	for i in count:
		var r := RunManager.rng.randf()
		var k: int
		match current_theme:
			RoomBuilder.RoomTheme.ORCHARD:
				k = Enemy.Kind.WEED if r < 0.55 else (Enemy.Kind.BUG if r < 0.85 else Enemy.Kind.FLYER)
			RoomBuilder.RoomTheme.CREEK:
				k = Enemy.Kind.BUG if r < 0.5 else (Enemy.Kind.FLYER if r < 0.85 else Enemy.Kind.WEED)
			RoomBuilder.RoomTheme.CLIFF:
				k = Enemy.Kind.FLYER if r < 0.45 else (Enemy.Kind.BUG if r < 0.8 else Enemy.Kind.WEED)
			RoomBuilder.RoomTheme.DUSK:
				k = Enemy.Kind.FLYER if r < 0.4 else (Enemy.Kind.WEED if r < 0.75 else Enemy.Kind.BUG)
			_:
				k = Enemy.Kind.BUG if r < 0.4 else (Enemy.Kind.WEED if r < 0.7 else Enemy.Kind.FLYER)
		var ex := RunManager.rng.randf_range(280.0, maxf(400.0, room_width - 180.0))
		var ey := (
			RunManager.rng.randf_range(280.0, GameConstants.GROUND_Y - 140.0)
			if k == Enemy.Kind.FLYER
			else GameConstants.GROUND_Y
		)
		_spawn_enemy(k, Vector2(ex, ey), scale_f)


func _spawn_enemy(kind: int, pos: Vector2, scale_f: float) -> void:
	var e: CharacterBody2D = enemy_scene.instantiate()
	e.setup(kind, scale_f, room_width)
	entities.add_child(e)
	if e.has_method("bind_spawn"):
		e.call("bind_spawn", pos)
	else:
		e.global_position = pos
	e.died.connect(_on_enemy_died)


func _living_enemy_count() -> int:
	var left := 0
	for c in get_tree().get_nodes_in_group("enemy"):
		if not is_instance_valid(c) or c.is_queued_for_deletion():
			continue
		# Ignore corpses already falling out of the world (belt-and-suspenders).
		if c is Node2D and (c as Node2D).global_position.y > GameConstants.VIEW_H + 20.0:
			continue
		left += 1
	return left


func _on_enemy_died() -> void:
	_shake = minf(1.0, _shake + 0.35)
	call_deferred("_check_room_clear")


func _check_room_clear() -> void:
	if _cleared or RunManager.mode != "play":
		return
	if _living_enemy_count() > 0:
		return
	_cleared = true
	_clear_projectiles()
	_spawn_door()
	RunManager.room_cleared.emit()
	if hud and hud.has_method("show_clear_hint"):
		hud.call("show_clear_hint")


func _spawn_door() -> void:
	if RunManager.mode != "play":
		return
	if door and is_instance_valid(door):
		door.queue_free()
	door = door_scene.instantiate()
	entities.add_child(door)
	var px := GameConstants.VIEW_W * 0.5
	if player and is_instance_valid(player):
		px = player.global_position.x
	var door_x := clampf(px + 220.0, 200.0, maxf(260.0, room_width - 100.0))
	door.global_position = Vector2(door_x, GameConstants.GROUND_Y)
	door.body_entered.connect(_on_door_entered)
	_shake = minf(1.0, _shake + 0.55)


func _on_door_entered(body: Node) -> void:
	if body.is_in_group("player") and RunManager.mode == "play":
		RunManager.offer_upgrades()


func _on_player_died() -> void:
	_shake = 1.0
	if player and is_instance_valid(player):
		player.enable_control(false)
	_clear_projectiles()


func _clear_projectiles() -> void:
	if not projectiles:
		return
	for c in projectiles.get_children():
		c.queue_free()


func spawn_projectile(node: Node) -> void:
	projectiles.add_child(node)


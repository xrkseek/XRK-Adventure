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
@onready var character_select_ui: Control = %CharacterSelectUI
@onready var settings_ui: Control = %SettingsUI
@onready var touch_controls: CanvasLayer = %TouchControls


var player: CharacterBody2D
var door: Area2D
var room_width: float = 1200.0
var _shake: float = 0.0
var _cleared: bool = false
var _room_gen: int = 0
var _title_petals: Array[Sprite2D] = []
var _on_title: bool = true
var _ambient_t: float = 0.0
var _bg_anim_t: float = 0.0
var _bg_anim_i: int = 0
var _bg_anim_textures: Array[Texture2D] = []
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
	if character_select_ui:
		character_select_ui.visible = false
	if settings_ui:
		settings_ui.visible = false
		if settings_ui.has_signal("closed") and not settings_ui.closed.is_connected(_on_settings_closed):
			settings_ui.closed.connect(_on_settings_closed)
		if settings_ui.has_signal("quit_to_title_requested") and not settings_ui.quit_to_title_requested.is_connected(_on_quit_to_title):
			settings_ui.quit_to_title_requested.connect(_on_quit_to_title)
	if touch_controls and touch_controls.has_method("set_gameplay_visible"):
		touch_controls.call("set_gameplay_visible", false)
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
	open_character_select()
	await get_tree().process_frame
	if character_select_ui and character_select_ui.has_method("_on_confirm"):
		character_select_ui.call("_on_confirm")
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


func _unhandled_input(event: InputEvent) -> void:
	## 用 unhandled：按钮/滑条吃掉的点击不会再误触发开局。
	if settings_ui and settings_ui.visible:
		if event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel"):
			settings_ui.call("close")
			get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("pause"):
		_toggle_settings_from_pause()
		get_viewport().set_input_as_handled()
		return
	if not _is_menu_mode():
		return
	if event.is_echo() or not event.is_pressed():
		return
	# 鼠标点 UI 已由 Control 处理；这里只认键盘/手柄确认，绝不认射击键。
	if event is InputEventMouseButton:
		return
	if character_select_ui and character_select_ui.visible:
		if event.is_action_pressed("ui_cancel"):
			show_title_menu()
			get_viewport().set_input_as_handled()
			return
		if _event_requests_menu_confirm(event):
			if character_select_ui.has_method("_on_confirm"):
				character_select_ui.call("_on_confirm")
			get_viewport().set_input_as_handled()
		return
	if title_ui and title_ui.visible and _event_requests_menu_confirm(event):
		open_character_select()
		get_viewport().set_input_as_handled()
	elif end_ui and end_ui.visible and _event_requests_menu_confirm(event):
		RunManager.start_run()
		get_viewport().set_input_as_handled()


func open_settings(from_pause: bool = false) -> void:
	if settings_ui == null:
		return
	if from_pause and RunManager.mode == "play":
		get_tree().paused = true
		if player and is_instance_valid(player):
			player.enable_control(false)
	settings_ui.call("open", from_pause)


func _toggle_settings_from_pause() -> void:
	if settings_ui and settings_ui.visible:
		settings_ui.call("close")
		return
	if RunManager.mode == "play":
		open_settings(true)
	elif RunManager.mode == "title" or _on_title:
		open_settings(false)


func _on_settings_closed() -> void:
	get_tree().paused = false
	if RunManager.mode == "play" and player and is_instance_valid(player):
		player.enable_control(true)
	if title_ui and title_ui.visible:
		var settings_btn := title_ui.get_node_or_null("%SettingsButton")
		if settings_btn and settings_btn is BaseButton:
			(settings_btn as BaseButton).grab_focus()
		else:
			var start_btn := title_ui.get_node_or_null("%StartButton")
			if start_btn and start_btn is BaseButton:
				(start_btn as BaseButton).grab_focus()


func _on_quit_to_title() -> void:
	get_tree().paused = false
	RunManager.mode = "title"
	if touch_controls and touch_controls.has_method("set_gameplay_visible"):
		touch_controls.call("set_gameplay_visible", false)
	_clear_world_scene()
	hud.visible = false
	upgrade_ui.visible = false
	end_ui.visible = false
	show_title_menu()


func open_character_select() -> void:
	title_ui.visible = false
	end_ui.visible = false
	if has_node("CharSelectLayer"):
		$CharSelectLayer.visible = true
	if character_select_ui and character_select_ui.has_method("open_select"):
		character_select_ui.call("open_select")


func show_title_menu() -> void:
	RunManager.mode = "title"
	end_ui.visible = false
	if character_select_ui and character_select_ui.has_method("close_select"):
		character_select_ui.call("close_select")
	_clear_world_scene()
	_show_title_bg()
	if title_ui.has_method("_setup_logo"):
		title_ui.call("_setup_logo")
	var start_btn := title_ui.get_node_or_null("%StartButton")
	if start_btn and start_btn is BaseButton:
		(start_btn as BaseButton).grab_focus()


func _process(delta: float) -> void:
	_shake = maxf(0.0, _shake - delta * 1.6)
	_ambient_t += delta
	_tick_title_petals(delta)
	_tick_bg_anim(delta)
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
		var trauma := _shake * _shake * (Settings.shake_mul() if Settings else 1.0)
		camera.offset = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * 14.0 * trauma


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


func _sheet_atlas_frames(path: String, frame_count: int, frame_w: int = 0, frame_h: int = 0) -> Array[Texture2D]:
	var out: Array[Texture2D] = []
	var tex: Texture2D = load(path)
	if tex == null:
		push_warning("Missing bg sheet: " + path)
		return out
	# 未指定则按横条均分（一张长图切两半 → 超宽帧）
	if frame_w <= 0:
		frame_w = int(tex.get_width() / float(maxi(1, frame_count)))
	if frame_h <= 0:
		frame_h = tex.get_height()
	for i in frame_count:
		var at := AtlasTexture.new()
		at.atlas = tex
		at.filter_clip = true
		at.region = Rect2(i * frame_w, 0, frame_w, frame_h)
		out.append(at)
	return out


func _fit_wide_bg(tex: Texture2D, cover_w: float, cover_h: float) -> void:
	## 高度对齐视口；宽度 = 图本身×scale，不硬撑房间。
	if tex == null:
		return
	var tw := float(tex.get_width())
	var th := float(tex.get_height())
	if tw < 1.0 or th < 1.0:
		return
	var s := cover_h / th
	bg.texture = tex
	bg.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	bg.centered = false
	bg.scale = Vector2(s, s)
	var drawn_w := tw * s
	var drawn_h := th * s
	# 标题居中；局内贴左，宽度即背景宽
	var x := (cover_w - drawn_w) * 0.5 if _on_title else 0.0
	bg.position = Vector2(x, (cover_h - drawn_h) * 0.5)
	bg.set_meta("drawn_w", drawn_w)


func _tick_bg_anim(delta: float) -> void:
	if _bg_anim_textures.is_empty():
		return
	_bg_anim_t += delta
	if _bg_anim_t < 1.0 / SpriteFactory.BG_FPS:
		return
	_bg_anim_t = 0.0
	_bg_anim_i = (_bg_anim_i + 1) % _bg_anim_textures.size()
	var tex := _bg_anim_textures[_bg_anim_i]
	_fit_wide_bg(tex, GameConstants.VIEW_W, GameConstants.VIEW_H)
	if not _on_title:
		bg.set_meta("cover_w", float(bg.get_meta("drawn_w", GameConstants.VIEW_W)))


func _is_menu_mode() -> bool:
	return RunManager.mode == "title" or RunManager.mode == "dead" or RunManager.mode == "win"


func _event_requests_menu_confirm(event: InputEvent) -> bool:
	## 菜单确认：Enter / 手柄 A / 结算 R。不含射击、不含鼠标（鼠标走按钮）。
	if event.is_action_pressed("confirm") or event.is_action_pressed("ui_accept"):
		return true
	if (RunManager.mode == "dead" or RunManager.mode == "win") and event.is_action_pressed("restart"):
		return true
	if event is InputEventJoypadButton:
		return (event as InputEventJoypadButton).button_index == JOY_BUTTON_A
	if event is InputEventKey:
		var k := event as InputEventKey
		if (
			k.keycode == KEY_ENTER
			or k.keycode == KEY_KP_ENTER
			or k.physical_keycode == KEY_ENTER
			or k.physical_keycode == KEY_KP_ENTER
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
	if has_node("CharSelectLayer"):
		$CharSelectLayer.visible = true
	title_ui.visible = true
	title_ui.mouse_filter = Control.MOUSE_FILTER_STOP
	if character_select_ui:
		character_select_ui.visible = false
	# 单层场景；不拼 mid
	if mid_bg:
		mid_bg.visible = false
	_bg_anim_textures = _sheet_atlas_frames("res://assets/bg/scene_title_sheet.png", SpriteFactory.BG_FRAMES)
	if _bg_anim_textures.is_empty():
		_bg_anim_textures = _sheet_atlas_frames("res://assets/bg/scene_title.png", 1)
	_bg_anim_i = 0
	_bg_anim_t = 0.0
	_fit_wide_bg(
		_bg_anim_textures[0] if not _bg_anim_textures.is_empty() else null,
		GameConstants.VIEW_W,
		GameConstants.VIEW_H
	)
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
	if has_node("CharSelectLayer"):
		$CharSelectLayer.visible = false
	title_ui.visible = false
	if character_select_ui:
		character_select_ui.visible = false
	end_ui.visible = false
	upgrade_ui.visible = false
	hud.visible = true
	get_viewport().gui_release_focus()
	if touch_controls and touch_controls.has_method("set_gameplay_visible"):
		touch_controls.call("set_gameplay_visible", true)
	_build_room()


func _on_run_ended(_victory: bool) -> void:
	if touch_controls and touch_controls.has_method("set_gameplay_visible"):
		touch_controls.call("set_gameplay_visible", false)
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


func _clear_world_scene() -> void:
	## 回标题：清掉平台/装饰/云/实体，只留标题风景。
	_clear_layer(platforms)
	_clear_layer(decor_back)
	_clear_layer(decor_front)
	_clear_layer(clouds)
	_clear_layer(entities)
	_clear_projectiles()
	player = null
	door = null


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
	# 背景宽度 = 图自身铺高后的宽度，不硬撑房间
	if mid_bg:
		mid_bg.visible = false
	_bg_anim_textures = _sheet_atlas_frames(RoomBuilder.sky_sheet_path(current_theme), SpriteFactory.BG_FRAMES)
	if _bg_anim_textures.is_empty():
		_bg_anim_textures = _sheet_atlas_frames(RoomBuilder.sky_path(current_theme), 1)
	_bg_anim_i = 0
	_bg_anim_t = 0.0
	_fit_wide_bg(
		_bg_anim_textures[0] if not _bg_anim_textures.is_empty() else null,
		GameConstants.VIEW_W,
		GameConstants.VIEW_H
	)
	bg.set_meta("cover_w", float(bg.get_meta("drawn_w", GameConstants.VIEW_W)))

	var builder := RoomBuilder.new(RunManager.rng)
	builder.build(platforms, decor_back, decor_front, clouds, room_width, floor_n, current_theme)

	player = player_scene.instantiate()
	player.add_to_group("player")
	player.global_position = Vector2(110, GameConstants.GROUND_Y)
	entities.add_child(player)
	if player.has_method("bind_room"):
		player.call("bind_room", room_width)
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
	if not (body.is_in_group("player") and RunManager.mode == "play"):
		return
	if not player or not is_instance_valid(player):
		RunManager.offer_upgrades()
		return
	# 进门：角色缩进门内 + 门放大，再进强化
	if door and is_instance_valid(door) and door.body_entered.is_connected(_on_door_entered):
		door.body_entered.disconnect(_on_door_entered)
	player.enable_control(false)
	var tw := create_tween()
	tw.set_parallel(true)
	tw.tween_property(player, "global_position", door.global_position + Vector2(0, -24), 0.28).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_property(player, "scale", Vector2(0.12, 0.12), 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	tw.tween_property(player, "modulate:a", 0.0, 0.28)
	if door and is_instance_valid(door):
		tw.tween_property(door, "scale", Vector2(1.45, 1.45), 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.set_parallel(false)
	tw.tween_callback(func() -> void:
		RunManager.offer_upgrades()
	)


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


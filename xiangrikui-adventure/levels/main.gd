extends Node2D

@onready var world: Node2D = %World
@onready var entities: Node2D = %Entities
@onready var platforms: Node2D = %Platforms
@onready var projectiles: Node2D = %Projectiles
@onready var camera: Camera2D = %Camera
@onready var bg: Sprite2D = %Bg
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

var player_scene: PackedScene = preload("res://entities/player/player.tscn")
var enemy_scene: PackedScene = preload("res://entities/enemy/enemy.tscn")
var door_scene: PackedScene = preload("res://levels/door.tscn")


func _ready() -> void:
	RunManager.run_started.connect(_on_run_started)
	RunManager.run_ended.connect(_on_run_ended)
	RunManager.upgrade_offered.connect(_on_upgrade_offered)
	title_ui.visible = true
	upgrade_ui.visible = false
	end_ui.visible = false
	hud.visible = false
	_show_title_bg()
	if "--smoke-title" in OS.get_cmdline_user_args():
		call_deferred("_smoke_title_start")


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


func _input(event: InputEvent) -> void:
	# Runs before GUI. Focused Controls / Dim overlays must not block starting.
	if not _is_menu_mode():
		return
	if event.is_echo() or not event.is_pressed():
		return
	if _event_requests_start(event):
		RunManager.start_run()
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_shake = maxf(0.0, _shake - delta * 1.6)
	if player and RunManager.mode == "play" and is_instance_valid(player):
		var target := Vector2(player.global_position.x, 270.0)
		target.x = clampf(target.x, 480.0, maxf(480.0, room_width - 480.0))
		camera.global_position = camera.global_position.lerp(target, 1.0 - pow(0.001, delta))
		var trauma := _shake * _shake
		camera.offset = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * 14.0 * trauma


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
	bg.texture = load("res://assets/bg/sky.png")
	bg.centered = false
	bg.position = Vector2.ZERO
	bg.scale = Vector2(960.0 / 1536.0, 540.0 / 1024.0)


func _on_run_started() -> void:
	title_ui.visible = false
	end_ui.visible = false
	upgrade_ui.visible = false
	hud.visible = true
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
	RunManager.apply_upgrade(upgrade)
	if RunManager.mode == "play":
		_build_room()


func _build_room() -> void:
	_room_gen += 1
	_cleared = false
	for c in platforms.get_children():
		c.queue_free()
	for c in entities.get_children():
		c.queue_free()
	_clear_projectiles()
	door = null
	player = null

	var floor_n := RunManager.floor_num
	room_width = 1100.0 + floor_n * 40.0
	_show_title_bg()
	bg.scale = Vector2(room_width / 1536.0 * 1.1, 540.0 / 1024.0)

	# Ground
	_add_ground(0, 470, room_width, 90)

	# Platforms
	var plats := 4 + int(floor_n / 2)
	for i in plats:
		var pw := RunManager.rng.randf_range(120, 220)
		var px := RunManager.rng.randf_range(180, room_width - 280)
		var py := RunManager.rng.randf_range(180, 360)
		_add_platform(px, py, pw, 24)

	# Player
	player = player_scene.instantiate()
	player.add_to_group("player")
	entities.add_child(player)
	player.global_position = Vector2(90, 470)
	player.died.connect(_on_player_died)
	player.heal_full_from_stats()
	player.enable_control(true)
	camera.global_position = Vector2(480, 270)
	camera.make_current()

	# Enemies
	var is_boss := floor_n >= RunManager.MAX_FLOOR and RunManager.room_num == RunManager.ROOMS_PER_FLOOR - 1
	var scale_f := 1.0 + (floor_n - 1) * 0.12
	if is_boss:
		_spawn_enemy(Enemy.Kind.BOSS, Vector2(room_width * 0.55, 470), scale_f)
	else:
		var count := 3 + floor_n
		for i in count:
			var r := RunManager.rng.randf()
			var k: int
			if r < 0.45:
				k = Enemy.Kind.BUG
			elif r < 0.75:
				k = Enemy.Kind.WEED
			else:
				k = Enemy.Kind.FLYER
			var ex := RunManager.rng.randf_range(280, room_width - 160)
			var ey := 220.0 if k == Enemy.Kind.FLYER else 470.0
			_spawn_enemy(k, Vector2(ex, ey), scale_f)

	hud.call("refresh")


func _spawn_enemy(kind: int, pos: Vector2, scale_f: float) -> void:
	var e: CharacterBody2D = enemy_scene.instantiate()
	entities.add_child(e)
	e.global_position = pos
	e.setup(kind, scale_f, room_width)
	e.died.connect(_on_enemy_died)


func _on_enemy_died() -> void:
	_shake = minf(1.0, _shake + 0.35)
	var gen := _room_gen
	await get_tree().process_frame
	if gen != _room_gen or RunManager.mode != "play":
		return
	var left := 0
	for c in entities.get_children():
		if is_instance_valid(c) and c.is_in_group("enemy"):
			left += 1
	if left == 0 and not _cleared:
		_cleared = true
		_clear_projectiles()
		_spawn_door()
		RunManager.room_cleared.emit()


func _spawn_door() -> void:
	if RunManager.mode != "play":
		return
	door = door_scene.instantiate()
	entities.add_child(door)
	door.global_position = Vector2(room_width - 100, 390)
	door.body_entered.connect(_on_door_entered)


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


func _add_ground(x: float, y: float, w: float, h: float) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(w, h)
	shape.shape = rect
	shape.position = Vector2(w * 0.5, h * 0.5)
	body.add_child(shape)
	# visual
	var spr := ColorRect.new()
	spr.color = Color("7a5334")
	spr.size = Vector2(w, h)
	body.add_child(spr)
	var grass := ColorRect.new()
	grass.color = Color("2f7a45")
	grass.size = Vector2(w, 14)
	body.add_child(grass)
	platforms.add_child(body)
	body.position = Vector2(x, y)


func _add_platform(x: float, y: float, w: float, h: float) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(w, h)
	shape.shape = rect
	shape.position = Vector2(w * 0.5, h * 0.5)
	body.add_child(shape)
	var spr := Sprite2D.new()
	spr.texture = load("res://assets/tiles/platform.png")
	spr.centered = false
	spr.scale = Vector2(w / 96.0, h / 24.0)
	body.add_child(spr)
	platforms.add_child(body)
	body.position = Vector2(x, y)

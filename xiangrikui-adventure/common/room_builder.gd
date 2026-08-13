class_name RoomBuilder
extends RefCounted

## Builds themed rooms: layout + decor differ so runs feel varied.

enum RoomTheme { MEADOW, ORCHARD, CREEK, DUSK, CLIFF }

var _rng: RandomNumberGenerator
var _room_w: float = 1200.0
var theme: RoomTheme = RoomTheme.MEADOW


func _init(rng: RandomNumberGenerator) -> void:
	_rng = rng


static func pick_theme(floor_n: int, room_n: int, is_boss: bool) -> RoomTheme:
	if is_boss:
		return RoomTheme.DUSK
	var key := (floor_n * 3 + room_n) % 5
	match key:
		0:
			return RoomTheme.MEADOW
		1:
			return RoomTheme.ORCHARD
		2:
			return RoomTheme.CREEK
		3:
			return RoomTheme.CLIFF
		_:
			return RoomTheme.DUSK


static func theme_name(t: RoomTheme) -> String:
	match t:
		RoomTheme.MEADOW:
			return "向阳草地"
		RoomTheme.ORCHARD:
			return "果园小径"
		RoomTheme.CREEK:
			return "溪边青石"
		RoomTheme.DUSK:
			return "黄昏田野"
		RoomTheme.CLIFF:
			return "岩阶高台"
	return "鹿外"


static func sky_path(t: RoomTheme) -> String:
	match t:
		RoomTheme.DUSK:
			return "res://assets/bg/sky_dusk.png"
		RoomTheme.CREEK:
			return "res://assets/bg/sky_creek.png"
		_:
			return "res://assets/bg/sky.png"


func build(
	platforms: Node2D,
	decor_back: Node2D,
	decor_front: Node2D,
	clouds: Node2D,
	room_w: float,
	floor_n: int,
	room_theme: RoomTheme
) -> void:
	_room_w = room_w
	theme = room_theme
	_clear(platforms)
	_clear(decor_back)
	_clear(decor_front)
	_clear(clouds)

	_add_ground(platforms, 0.0, GameConstants.GROUND_Y, room_w, GameConstants.GROUND_H)
	_add_platform_course(platforms, floor_n)
	_scatter_decor(decor_back, decor_front, floor_n)
	_spawn_clouds(clouds)


func _clear(node: Node) -> void:
	if node == null:
		return
	for c in node.get_children():
		c.queue_free()


func _add_ground(parent: Node2D, x: float, y: float, w: float, h: float) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = GameConstants.LAYER_WORLD
	body.collision_mask = 0
	body.z_index = GameConstants.Z_PLATFORMS

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(w, h)
	shape.shape = rect
	shape.position = Vector2(w * 0.5, h * 0.5)
	body.add_child(shape)

	var ground_tex: Texture2D = load("res://assets/tiles/ground.png")
	var edge_tex: Texture2D = load("res://assets/tiles/grass_edge.png")
	# TILE = display width; stretch tex to exact TILE×GROUND_H (no gaps/overlap).
	var gtw := float(ground_tex.get_width())
	var gth := float(ground_tex.get_height())
	var etw := float(edge_tex.get_width())
	var eth := float(edge_tex.get_height())
	var edge_h := 10.0
	var tiles := int(ceili(w / GameConstants.TILE))
	for i in tiles:
		var dirt := Sprite2D.new()
		dirt.texture = ground_tex
		dirt.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		dirt.centered = false
		dirt.position = Vector2(i * GameConstants.TILE, 0)
		dirt.scale = Vector2(GameConstants.TILE / gtw, h / gth)
		if theme == RoomTheme.DUSK:
			dirt.modulate = Color(1.08, 0.92, 0.85)
		elif theme == RoomTheme.CREEK:
			dirt.modulate = Color(0.9, 0.95, 1.05)
		body.add_child(dirt)

		var grass := Sprite2D.new()
		grass.texture = edge_tex
		grass.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		grass.centered = false
		grass.position = Vector2(i * GameConstants.TILE, -edge_h)
		grass.scale = Vector2(GameConstants.TILE / etw, edge_h / eth)
		body.add_child(grass)

	parent.add_child(body)
	body.position = Vector2(x, y)


func _add_platform_course(parent: Node2D, floor_n: int) -> void:
	var course: Array = []
	match theme:
		RoomTheme.MEADOW:
			course = [
				{"x": 180.0, "y": GameConstants.PLAT_Y_LOW, "w": 200.0},
				{"x": 420.0, "y": GameConstants.PLAT_Y_MID, "w": 180.0},
				{"x": 680.0, "y": GameConstants.PLAT_Y_LOW, "w": 190.0},
				{"x": 920.0, "y": GameConstants.PLAT_Y_HIGH, "w": 170.0},
				{"x": 1140.0, "y": GameConstants.PLAT_Y_MID, "w": 160.0},
			]
		RoomTheme.ORCHARD:
			course = [
				{"x": 160.0, "y": GameConstants.PLAT_Y_LOW, "w": 160.0},
				{"x": 360.0, "y": GameConstants.PLAT_Y_LOW, "w": 150.0},
				{"x": 560.0, "y": GameConstants.PLAT_Y_MID, "w": 200.0},
				{"x": 820.0, "y": GameConstants.PLAT_Y_MID, "w": 160.0},
				{"x": 1040.0, "y": GameConstants.PLAT_Y_HIGH, "w": 180.0},
			]
		RoomTheme.CREEK:
			course = [
				{"x": 200.0, "y": GameConstants.PLAT_Y_LOW, "w": 140.0},
				{"x": 400.0, "y": GameConstants.PLAT_Y_LOW, "w": 130.0},
				{"x": 600.0, "y": GameConstants.PLAT_Y_MID, "w": 150.0},
				{"x": 820.0, "y": GameConstants.PLAT_Y_LOW, "w": 140.0},
				{"x": 1020.0, "y": GameConstants.PLAT_Y_MID, "w": 160.0},
				{"x": 1200.0, "y": GameConstants.PLAT_Y_HIGH, "w": 140.0},
			]
		RoomTheme.CLIFF:
			course = [
				{"x": 160.0, "y": GameConstants.PLAT_Y_LOW, "w": 150.0},
				{"x": 340.0, "y": GameConstants.PLAT_Y_MID, "w": 140.0},
				{"x": 520.0, "y": GameConstants.PLAT_Y_HIGH, "w": 140.0},
				{"x": 740.0, "y": GameConstants.PLAT_Y_MID, "w": 160.0},
				{"x": 960.0, "y": GameConstants.PLAT_Y_HIGH, "w": 150.0},
				{"x": 1160.0, "y": GameConstants.PLAT_Y_LOW, "w": 170.0},
			]
		RoomTheme.DUSK:
			course = [
				{"x": 200.0, "y": GameConstants.PLAT_Y_MID, "w": 220.0},
				{"x": 500.0, "y": GameConstants.PLAT_Y_LOW, "w": 180.0},
				{"x": 760.0, "y": GameConstants.PLAT_Y_HIGH, "w": 200.0},
				{"x": 1040.0, "y": GameConstants.PLAT_Y_MID, "w": 190.0},
			]
	for i in mini(2, floor_n):
		course.append({
			"x": _rng.randf_range(240.0, maxf(300.0, _room_w - 240.0)),
			"y": [GameConstants.PLAT_Y_LOW, GameConstants.PLAT_Y_MID, GameConstants.PLAT_Y_HIGH][_rng.randi() % 3],
			"w": _rng.randf_range(130.0, 190.0),
		})
	for p in course:
		if float(p["x"]) < _room_w - 100.0:
			_add_platform(parent, float(p["x"]), float(p["y"]), float(p["w"]), GameConstants.PLAT_THICKNESS)


func _add_platform(parent: Node2D, x: float, y: float, w: float, h: float) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = GameConstants.LAYER_WORLD
	body.collision_mask = 0
	body.z_index = GameConstants.Z_PLATFORMS

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(w, h)
	shape.shape = rect
	shape.position = Vector2(w * 0.5, h * 0.5)
	shape.one_way_collision = true
	shape.one_way_collision_margin = 4.0
	body.add_child(shape)

	var plat_tex: Texture2D = load("res://assets/tiles/platform.png")
	var segs := maxi(1, int(ceili(w / GameConstants.PLAT_TEX_W)))
	var seg_w := w / float(segs)
	for i in segs:
		var spr := Sprite2D.new()
		spr.texture = plat_tex
		spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		spr.centered = false
		spr.position = Vector2(i * seg_w, 0)
		spr.scale = Vector2(seg_w / GameConstants.PLAT_TEX_W, h / GameConstants.PLAT_TEX_H)
		body.add_child(spr)

	# Flowers / moss sit ON the plank (never dangling under).
	var moss_tex: Texture2D = load("res://assets/decor/moss.png")
	var flower_tex: Texture2D = load("res://assets/decor/flower.png")
	var flower_p: Texture2D = load("res://assets/decor/flower_pink.png")
	for i in range(2, int(w) - 20, 36):
		if _rng.randf() < 0.55:
			var moss := Sprite2D.new()
			moss.texture = moss_tex
			moss.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			moss.centered = false
			moss.position = Vector2(i, -6)
			moss.set_meta("ambient", "bob")
			moss.set_meta("phase", _rng.randf() * TAU)
			body.add_child(moss)
		elif _rng.randf() < 0.35:
			var fl := Sprite2D.new()
			fl.texture = flower_tex if _rng.randf() < 0.5 else flower_p
			fl.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			fl.position = Vector2(i + 8, -4)
			fl.offset = Vector2(0, -fl.texture.get_height() * 0.5)
			fl.set_meta("ambient", "sway")
			fl.set_meta("phase", _rng.randf() * TAU)
			fl.set_meta("base_rot", 0.0)
			body.add_child(fl)

	parent.add_child(body)
	body.position = Vector2(x, y)


func _scatter_decor(back: Node2D, front: Node2D, floor_n: int) -> void:
	var tree_tex: Texture2D = load("res://assets/decor/tree.png")
	var bush_tex: Texture2D = load("res://assets/decor/bush.png")
	var fence_tex: Texture2D = load("res://assets/decor/fence.png")
	var rock_tex: Texture2D = load("res://assets/decor/rock.png")
	var flower_tex: Texture2D = load("res://assets/decor/flower.png")
	var flower_p: Texture2D = load("res://assets/decor/flower_pink.png")
	var crop_tex: Texture2D = load("res://assets/decor/crop.png")

	var tree_chance := 0.55
	var tree_gap := Vector2(100.0, 170.0)
	match theme:
		RoomTheme.ORCHARD:
			tree_chance = 0.85
			tree_gap = Vector2(70.0, 110.0)
		RoomTheme.CREEK:
			tree_chance = 0.25
			tree_gap = Vector2(140.0, 220.0)
		RoomTheme.CLIFF:
			tree_chance = 0.2
			tree_gap = Vector2(160.0, 240.0)
		RoomTheme.DUSK:
			tree_chance = 0.4
			tree_gap = Vector2(120.0, 190.0)
		_:
			pass

	# Keep full canopy on-screen: inset by half tree width × max scale (~60px).
	var x := 90.0
	while x < _room_w - 90.0:
		if _rng.randf() < tree_chance:
			_prop(back, tree_tex, Vector2(x, GameConstants.GROUND_Y - 2), _rng.randf_range(0.85, 1.05), true)
		x += _rng.randf_range(tree_gap.x, tree_gap.y)

	if theme == RoomTheme.MEADOW or theme == RoomTheme.DUSK:
		for i in 8:
			_prop(front, fence_tex, Vector2(28 + i * 42, GameConstants.GROUND_Y), 1.0, false)

	for i in 10 + floor_n * 3:
		var dx := _rng.randf_range(150.0, _room_w - 100.0)
		var roll := _rng.randf()
		if theme == RoomTheme.CREEK or theme == RoomTheme.CLIFF:
			if roll < 0.55:
				_prop(front, rock_tex, Vector2(dx, GameConstants.GROUND_Y), _rng.randf_range(0.9, 1.3), true)
			elif roll < 0.75:
				_prop(front, bush_tex, Vector2(dx, GameConstants.GROUND_Y), 1.0, true)
			else:
				_prop(front, flower_tex, Vector2(dx, GameConstants.GROUND_Y), 1.0, false)
		elif theme == RoomTheme.ORCHARD:
			if roll < 0.4:
				_prop(front, bush_tex, Vector2(dx, GameConstants.GROUND_Y), 1.1, true)
			elif roll < 0.7:
				_prop(front, crop_tex, Vector2(dx, GameConstants.GROUND_Y), 1.0, false)
			else:
				_prop(front, flower_p, Vector2(dx, GameConstants.GROUND_Y), 1.0, false)
		else:
			if roll < 0.28:
				_prop(front, bush_tex, Vector2(dx, GameConstants.GROUND_Y), _rng.randf_range(0.9, 1.2), true)
			elif roll < 0.45:
				_prop(front, rock_tex, Vector2(dx, GameConstants.GROUND_Y), 1.0, true)
			elif roll < 0.7:
				_prop(front, flower_tex if _rng.randf() < 0.5 else flower_p, Vector2(dx, GameConstants.GROUND_Y), 1.0, false)
			else:
				_prop(front, crop_tex, Vector2(dx, GameConstants.GROUND_Y), 1.0, false)

	if theme == RoomTheme.MEADOW or theme == RoomTheme.ORCHARD:
		var patch := _room_w * 0.4
		for i in 6:
			for j in 2:
				_prop(front, crop_tex, Vector2(patch + i * 26 + j * 8, GameConstants.GROUND_Y - j * 2), 1.0, false)


func _prop(parent: Node2D, tex: Texture2D, pos: Vector2, scl: float, can_flip: bool) -> void:
	var s := Sprite2D.new()
	s.texture = tex
	s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	s.centered = true
	s.offset = Vector2(0, -tex.get_height() * 0.5)
	s.position = pos
	s.scale = Vector2(scl, scl)
	if can_flip and _rng.randf() < 0.5:
		s.flip_h = true
	var path := String(tex.resource_path)
	if "tree" in path or "bush" in path:
		s.set_meta("ambient", "sway")
		s.set_meta("amp", 0.035 if "tree" in path else 0.05)
	elif "crop" in path or "flower" in path:
		s.set_meta("ambient", "sway_bob")
		s.set_meta("amp", 0.06)
	s.set_meta("phase", _rng.randf() * TAU)
	s.set_meta("base_pos", pos)
	s.set_meta("base_rot", 0.0)
	parent.add_child(s)


func _spawn_clouds(clouds: Node2D) -> void:
	var tex: Texture2D = load("res://assets/decor/cloud.png")
	var n := 4 if theme == RoomTheme.DUSK else 6
	for i in n:
		var s := Sprite2D.new()
		s.texture = tex
		s.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		s.position = Vector2(_rng.randf_range(0, _room_w), _rng.randf_range(30, 140))
		s.modulate = Color(1, 0.9, 0.85, _rng.randf_range(0.45, 0.8)) if theme == RoomTheme.DUSK else Color(1, 1, 1, _rng.randf_range(0.5, 0.85))
		s.scale = Vector2.ONE * _rng.randf_range(0.7, 1.3)
		s.set_meta("spd", _rng.randf_range(5.0, 16.0))
		clouds.add_child(s)


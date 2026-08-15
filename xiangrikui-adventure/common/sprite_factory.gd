class_name SpriteFactory
extends RefCounted

## Atlas → SpriteFrames. Character sheets live under assets/characters/<id>/anim/.
## Sheet size MUST match profile; stale Godot imports → empty frames (idle「隐身」).

const DEFAULT_CHARACTER_ID := "xuyuezhen"

const BUG_W := 72
const BUG_H := 56
const WEED_W := 64
const WEED_H := 88
const FLYER_W := 128
const FLYER_H := 96
const BOSS_W := 240
const BOSS_H := 240
const TITLE_LOGO_W := 710
const TITLE_LOGO_H := 440
const TITLE_LOGO_FRAMES := 4
const TITLE_LOGO_FPS := 5.0
const BG_SKY_W := 960
const BG_SKY_H := 360
const BG_MID_W := 960
const BG_MID_H := 280
const BG_TITLE_W := 960
const BG_TITLE_H := 540
const BG_FRAMES := 2
const BG_FPS := 0.45  # 超宽双帧慢播


static func _new_frames() -> SpriteFrames:
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")
	return sf


static func active_character_id() -> String:
	var tree := Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var rm := tree.root.get_node_or_null("/root/RunManager")
		if rm != null and str(rm.get("character_id")) != "":
			return str(rm.get("character_id"))
	return DEFAULT_CHARACTER_ID


static func character_dir(char_id: String = "") -> String:
	if char_id.is_empty():
		char_id = active_character_id()
	return "res://assets/characters/%s" % char_id


static func load_character_profile(char_id: String = "") -> Dictionary:
	if char_id.is_empty():
		char_id = active_character_id()
	var path := "%s/character.json" % character_dir(char_id)
	if not FileAccess.file_exists(path):
		push_error("Missing character profile: " + path)
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Cannot open " + path)
		return {}
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		push_error("Invalid character.json: " + path)
		return {}
	return data


static func make_player_frames() -> SpriteFrames:
	return make_character_frames(active_character_id())


static func make_character_frames(char_id: String = "") -> SpriteFrames:
	if char_id.is_empty():
		char_id = active_character_id()
	var profile := load_character_profile(char_id)
	var sf := _new_frames()
	if profile.is_empty():
		return sf
	var cell_w := int(profile.get("cell_w", 64)) * int(profile.get("px", 2))
	var cell_h := int(profile.get("cell_h", 68)) * int(profile.get("px", 2))
	var states: Dictionary = profile.get("states", {})
	for state_name in states.keys():
		var st: Dictionary = states[state_name]
		var path := "%s/anim/%s_sheet.png" % [character_dir(char_id), state_name]
		var dirs: Array = st.get("dirs", [])
		if str(state_name) == "attack" and dirs.size() > 0:
			_add_dir_attack_anims(
				sf,
				path,
				dirs,
				int(st.get("frames", 1)),
				cell_w,
				cell_h,
				float(st.get("fps", 12.0)),
				bool(st.get("loop", false))
			)
		else:
			_add_sheet_anim(
				sf,
				str(state_name),
				path,
				int(st.get("frames", 1)),
				cell_w,
				cell_h,
				float(st.get("fps", 8.0)),
				bool(st.get("loop", true))
			)
	return sf


## 右半平面 5 向（e/ne/n/se/s）；左半用 flip_h 镜像。
static func attack_base_dir_key(aim: Vector2) -> String:
	var d := aim.normalized() if aim.length_squared() > 0.0001 else Vector2.RIGHT
	var ang := d.angle()  # -PI..PI，0=右，-PI/2=上
	# 折到右半平面再分类
	var a := ang
	if absf(a) > PI * 0.5:
		a = PI - a if a > 0.0 else -PI - a
	# 右半：-90..+90 → n / ne / e / se / s
	if a <= -PI * 0.375:
		return "n"
	if a <= -PI * 0.125:
		return "ne"
	if a < PI * 0.125:
		return "e"
	if a < PI * 0.375:
		return "se"
	return "s"


static func attack_anim_name_for_aim(aim: Vector2, profile: Dictionary) -> StringName:
	var st: Dictionary = profile.get("states", {}).get("attack", {})
	var dirs: Array = st.get("dirs", [])
	if dirs.is_empty():
		return &"attack"
	var key := attack_base_dir_key(aim)
	var anim := "attack_%s" % key
	return StringName(anim)


static func attack_anim_flip_h(aim: Vector2, _profile: Dictionary) -> bool:
	## 左半平面镜像右半向帧
	return aim.x < -0.2


static func _add_dir_attack_anims(
	sf: SpriteFrames,
	path: String,
	dirs: Array,
	frame_count: int,
	frame_w: int,
	frame_h: int,
	speed: float,
	loop: bool
) -> void:
	var tex: Texture2D = load(path)
	if tex == null:
		push_error("Missing texture: " + path)
		return
	var rows := dirs.size()
	var expect_w := frame_count * frame_w
	var expect_h := rows * frame_h
	var tw := tex.get_width()
	var th := tex.get_height()
	if tw != expect_w or th != expect_h:
		push_error(
			"Dir attack sheet mismatch %s: got %dx%d, expected %dx%d (%d dirs × %d frames)."
			% [path, tw, th, expect_w, expect_h, rows, frame_count]
		)
	for r in rows:
		var dir_key := str(dirs[r])
		var anim_name := "attack_%s" % dir_key
		if sf.has_animation(anim_name):
			sf.remove_animation(anim_name)
		sf.add_animation(anim_name)
		sf.set_animation_speed(anim_name, speed)
		sf.set_animation_loop(anim_name, loop)
		for c in frame_count:
			var at := AtlasTexture.new()
			at.atlas = tex
			at.filter_clip = true
			at.region = Rect2(c * frame_w, r * frame_h, frame_w, frame_h)
			sf.add_frame(anim_name, at)
	# 兼容旧逻辑：attack = attack_e
	if sf.has_animation("attack_e"):
		if sf.has_animation("attack"):
			sf.remove_animation("attack")
		sf.add_animation("attack")
		sf.set_animation_speed("attack", speed)
		sf.set_animation_loop("attack", loop)
		for i in sf.get_frame_count("attack_e"):
			sf.add_frame("attack", sf.get_frame_texture("attack_e", i))


static func player_cell_size(char_id: String = "") -> Vector2i:
	var profile := load_character_profile(char_id)
	if profile.is_empty():
		return Vector2i(128, 136)
	return Vector2i(
		int(profile.get("cell_w", 64)) * int(profile.get("px", 2)),
		int(profile.get("cell_h", 68)) * int(profile.get("px", 2))
	)


static func make_bug_frames() -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(sf, "walk", "res://assets/enemies/anim/enemy_bug_sheet.png", 4, BUG_W, BUG_H, 8.0, true)
	return sf


static func make_weed_frames() -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(sf, "idle", "res://assets/enemies/anim/enemy_weed_sheet.png", 4, WEED_W, WEED_H, 5.0, true)
	return sf


static func make_flyer_frames() -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(sf, "fly", "res://assets/enemies/anim/enemy_flyer_sheet.png", 4, FLYER_W, FLYER_H, 12.0, true)
	return sf


static func make_title_logo_frames() -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(
		sf,
		"idle",
		"res://assets/ui/title_logo_sheet.png",
		TITLE_LOGO_FRAMES,
		TITLE_LOGO_W,
		TITLE_LOGO_H,
		TITLE_LOGO_FPS,
		true
	)
	return sf


static func make_bg_frames(sheet_path: String, frame_w: int, frame_h: int, fps: float = BG_FPS) -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(sf, "idle", sheet_path, BG_FRAMES, frame_w, frame_h, fps, true)
	return sf


static func make_boss_frames() -> SpriteFrames:
	var sf := _new_frames()
	_add_sheet_anim(sf, "idle", "res://assets/enemies/anim/enemy_boss_sheet.png", 4, BOSS_W, BOSS_H, 6.0, true)
	_add_sheet_anim(sf, "walk", "res://assets/enemies/anim/enemy_boss_walk_sheet.png", 6, BOSS_W, BOSS_H, 10.0, true)
	_add_sheet_anim(sf, "attack", "res://assets/enemies/anim/enemy_boss_attack_sheet.png", 6, BOSS_W, BOSS_H, 12.0, false)
	return sf


static func _add_sheet_anim(
	sf: SpriteFrames,
	anim_name: String,
	path: String,
	frame_count: int,
	frame_w: int,
	frame_h: int,
	speed: float,
	loop: bool
) -> void:
	var tex: Texture2D = load(path)
	if tex == null:
		push_error("Missing texture: " + path)
		return
	var tw := tex.get_width()
	var th := tex.get_height()
	var expect_w := frame_count * frame_w
	if tw != expect_w or th != frame_h:
		push_error(
			"Sheet size mismatch %s: got %dx%d, expected %dx%d (%d×%dx%d). Reimport or reprocess."
			% [path, tw, th, expect_w, frame_h, frame_count, frame_w, frame_h]
		)
		frame_count = mini(frame_count, maxi(1, int(tw / float(frame_w))))
		if th < frame_h:
			frame_h = th
	if sf.has_animation(anim_name):
		sf.remove_animation(anim_name)
	sf.add_animation(anim_name)
	sf.set_animation_speed(anim_name, speed)
	sf.set_animation_loop(anim_name, loop)
	for i in frame_count:
		var at := AtlasTexture.new()
		at.atlas = tex
		at.filter_clip = true
		at.region = Rect2(i * frame_w, 0, frame_w, frame_h)
		sf.add_frame(anim_name, at)

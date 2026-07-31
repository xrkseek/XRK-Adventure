class_name SpriteFactory
extends RefCounted

## Builds SpriteFrames from painted sheets at runtime (animation-ready).

static func make_player_frames() -> SpriteFrames:
	var sf := SpriteFrames.new()
	_add_sheet_anim(sf, "idle", "res://assets/sprites/anim/player_idle_sheet.png", 2, 128, 160, 5.0, true)
	_add_sheet_anim(sf, "walk", "res://assets/sprites/anim/player_walk_sheet.png", 2, 128, 160, 8.0, true)
	_add_sheet_anim(sf, "jump", "res://assets/sprites/anim/player_jump_sheet.png", 1, 128, 160, 5.0, true)
	return sf


static func make_flyer_frames() -> SpriteFrames:
	var sf := SpriteFrames.new()
	_add_sheet_anim(sf, "fly", "res://assets/sprites/anim/enemy_flyer_sheet.png", 2, 96, 80, 10.0, true)
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
	if sf.has_animation(anim_name):
		sf.remove_animation(anim_name)
	sf.add_animation(anim_name)
	sf.set_animation_speed(anim_name, speed)
	sf.set_animation_loop(anim_name, loop)
	for i in frame_count:
		var at := AtlasTexture.new()
		at.atlas = tex
		at.region = Rect2(i * frame_w, 0, frame_w, frame_h)
		sf.add_frame(anim_name, at)

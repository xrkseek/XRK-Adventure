extends Control

## Title overlay. 「开始历险」→ 选角；设置 / 退出。

@onready var hint: Label = %Hint
@onready var start_btn: Button = %StartButton
@onready var settings_btn: Button = %SettingsButton
@onready var quit_btn: Button = %QuitButton
@onready var title_logo: AnimatedSprite2D = %TitleLogo
@onready var sub_label: Label = get_node_or_null("Sub") as Label


func _ready() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_NONE
	_setup_logo()
	_layout_title()
	_ignore_mouse_on_decorations()
	if start_btn:
		start_btn.pressed.connect(_on_start_pressed)
		start_btn.grab_focus()
	if settings_btn:
		settings_btn.pressed.connect(_on_settings_pressed)
	if quit_btn:
		quit_btn.pressed.connect(_on_quit_pressed)
		quit_btn.visible = not OS.has_feature("web")
	resized.connect(_layout_title)


func _setup_logo() -> void:
	if title_logo == null:
		return
	title_logo.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	title_logo.sprite_frames = SpriteFactory.make_title_logo_frames()
	title_logo.play("idle")
	_layout_title()


func _layout_title() -> void:
	var w := size.x if size.x > 1.0 else GameConstants.VIEW_W
	var h := size.y if size.y > 1.0 else GameConstants.VIEW_H
	var btn_stack := 152.0 if quit_btn and quit_btn.visible else 108.0
	if title_logo:
		var target_w := minf(w * 0.96, 1240.0)
		var s := target_w / float(SpriteFactory.TITLE_LOGO_W)
		title_logo.scale = Vector2(s, s)
		var logo_h := float(SpriteFactory.TITLE_LOGO_H) * s
		var max_logo_top := 8.0
		var logo_cy := max_logo_top + logo_h * 0.5
		var need_ui := 48.0 + btn_stack
		if logo_cy + logo_h * 0.5 + need_ui > h - 12.0:
			var allow_h := h - 12.0 - need_ui - max_logo_top
			s = minf(s, allow_h / float(SpriteFactory.TITLE_LOGO_H))
			title_logo.scale = Vector2(s, s)
			logo_h = float(SpriteFactory.TITLE_LOGO_H) * s
			logo_cy = max_logo_top + logo_h * 0.5
		title_logo.position = Vector2(w * 0.5, logo_cy)
		var below := title_logo.position.y + logo_h * 0.5 + 6.0
		if sub_label:
			sub_label.offset_top = below
			sub_label.offset_bottom = below + 24.0
		if hint:
			hint.offset_top = below + 26.0
			hint.offset_bottom = below + 50.0
		var by := below + 56.0
		_place_btn(start_btn, by, 48.0)
		by += 52.0
		_place_btn(settings_btn, by, 40.0)
		by += 44.0
		if quit_btn and quit_btn.visible:
			_place_btn(quit_btn, by, 40.0)
		var max_bottom := h - 16.0
		var last := quit_btn if quit_btn and quit_btn.visible else settings_btn
		if last and last.offset_bottom > max_bottom:
			var shift := last.offset_bottom - max_bottom
			for b in [start_btn, settings_btn, quit_btn]:
				if b:
					b.offset_top -= shift
					b.offset_bottom -= shift
			if sub_label:
				sub_label.offset_top -= shift
				sub_label.offset_bottom -= shift
			if hint:
				hint.offset_top -= shift
				hint.offset_bottom -= shift


func _place_btn(btn: Button, top: float, height: float) -> void:
	if btn == null:
		return
	btn.offset_top = top
	btn.offset_bottom = top + height


func _ignore_mouse_on_decorations() -> void:
	var interactive: Array = [start_btn, settings_btn, quit_btn]
	for child in get_children():
		if child in interactive:
			continue
		if child is Control:
			(child as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE


func _on_start_pressed() -> void:
	_release_focus()
	var main := get_tree().current_scene
	if main and main.has_method("open_character_select"):
		main.open_character_select()
	else:
		RunManager.start_run()


func _on_settings_pressed() -> void:
	_release_focus()
	var main := get_tree().current_scene
	if main and main.has_method("open_settings"):
		main.open_settings(false)


func _on_quit_pressed() -> void:
	get_tree().quit()


func _release_focus() -> void:
	if start_btn:
		start_btn.release_focus()
	get_viewport().gui_release_focus()

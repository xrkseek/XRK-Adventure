extends Control

## 选角：读 assets/characters/<id>/character.json（跳过 _template）。

@onready var roster: HBoxContainer = %Roster
@onready var confirm_btn: Button = %ConfirmButton
@onready var back_btn: Button = %BackButton
@onready var name_label: Label = %NameLabel
@onready var preview: TextureRect = %Preview

var _selected_id: String = "xuyuezhen"
var _entries: Array[Dictionary] = []


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	if confirm_btn:
		confirm_btn.pressed.connect(_on_confirm)
	if back_btn:
		back_btn.pressed.connect(_on_back)


func open_select() -> void:
	visible = true
	_rebuild_roster()
	if confirm_btn:
		confirm_btn.grab_focus()


func close_select() -> void:
	visible = false
	get_viewport().gui_release_focus()


func _rebuild_roster() -> void:
	_entries.clear()
	for c in roster.get_children():
		c.queue_free()
	var dir := DirAccess.open("res://assets/characters")
	if dir == null:
		push_error("Missing characters dir")
		return
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if dir.current_is_dir() and not name.begins_with(".") and name != "_template":
			var profile := SpriteFactory.load_character_profile(name)
			if not profile.is_empty():
				_entries.append(profile)
		name = dir.get_next()
	dir.list_dir_end()
	_entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("id", "")) < str(b.get("id", ""))
	)
	if _entries.is_empty():
		name_label.text = "暂无可选角色"
		confirm_btn.disabled = true
		return
	confirm_btn.disabled = false
	if not _has_id(_selected_id):
		_selected_id = str(_entries[0].get("id", "xuyuezhen"))
	for p in _entries:
		var id := str(p.get("id", ""))
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(140, 48)
		btn.toggle_mode = true
		btn.set_pressed_no_signal(id == _selected_id)
		btn.text = str(p.get("display_name", id))
		btn.set_meta("char_id", id)
		btn.pressed.connect(_select.bind(id))
		roster.add_child(btn)
	_refresh_labels()


func _has_id(id: String) -> bool:
	for p in _entries:
		if str(p.get("id", "")) == id:
			return true
	return false


func _select(id: String) -> void:
	_selected_id = id
	for c in roster.get_children():
		if c is Button:
			(c as Button).set_pressed_no_signal(str(c.get_meta("char_id", "")) == id)
	_refresh_labels()


func _display_name(id: String) -> String:
	for p in _entries:
		if str(p.get("id", "")) == id:
			return str(p.get("display_name", id))
	return id


func _refresh_labels() -> void:
	name_label.text = "出征：%s" % _display_name(_selected_id)
	_update_preview(_selected_id)


func _update_preview(id: String) -> void:
	if preview == null:
		return
	var profile := SpriteFactory.load_character_profile(id)
	var cell_w := int(profile.get("cell_w", 64)) * int(profile.get("px", 2))
	var cell_h := int(profile.get("cell_h", 68)) * int(profile.get("px", 2))
	var path := "res://assets/characters/%s/anim/idle_sheet.png" % id
	if not ResourceLoader.exists(path):
		preview.texture = null
		return
	var tex: Texture2D = load(path)
	var at := AtlasTexture.new()
	at.atlas = tex
	at.filter_clip = true
	at.region = Rect2(0, 0, cell_w, cell_h)
	preview.texture = at


func _on_confirm() -> void:
	if _selected_id.is_empty():
		return
	RunManager.character_id = _selected_id
	close_select()
	RunManager.start_run()


func _on_back() -> void:
	close_select()
	var main := get_tree().current_scene
	if main and main.has_method("show_title_menu"):
		main.show_title_menu()

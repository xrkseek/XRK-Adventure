extends CanvasLayer

@onready var hearts: HBoxContainer = %Hearts
@onready var floor_label: Label = %FloorLabel
@onready var kill_label: Label = %KillLabel
@onready var clear_hint: Label = %ClearHint

var _theme_name: String = ""


func _ready() -> void:
	RunManager.stats_changed.connect(refresh)
	if clear_hint:
		clear_hint.visible = false
	refresh()


func refresh(theme_name: String = "") -> void:
	if theme_name != "":
		_theme_name = theme_name
	if clear_hint:
		clear_hint.visible = false
	for c in hearts.get_children():
		c.queue_free()
	var max_hp: int = int(RunManager.player_stats["max_hp"])
	var hp: int = int(RunManager.player_stats["hp"])
	for i in max_hp:
		var tex := TextureRect.new()
		tex.texture = load("res://assets/ui/heart.png" if i < hp else "res://assets/ui/heart_empty.png")
		tex.custom_minimum_size = Vector2(28, 28)
		tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		hearts.add_child(tex)
	var place := _theme_name if _theme_name != "" else "野外"
	floor_label.text = "第 %d 层 · %s · 房 %d/%d" % [
		RunManager.floor_num, place, RunManager.room_num + 1, RunManager.ROOMS_PER_FLOOR
	]
	kill_label.text = "击杀 %d" % RunManager.kills


func show_clear_hint() -> void:
	if clear_hint == null:
		return
	clear_hint.visible = true
	clear_hint.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(clear_hint, "modulate:a", 1.0, 0.25)
	tw.tween_interval(2.2)
	tw.tween_property(clear_hint, "modulate:a", 0.65, 0.4)

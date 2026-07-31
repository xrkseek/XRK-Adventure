extends CanvasLayer

@onready var hearts: HBoxContainer = %Hearts
@onready var floor_label: Label = %FloorLabel
@onready var kill_label: Label = %KillLabel


func _ready() -> void:
	RunManager.stats_changed.connect(refresh)
	refresh()


func refresh() -> void:
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
	floor_label.text = "第 %d 层 · 房间 %d/%d" % [RunManager.floor_num, RunManager.room_num + 1, RunManager.ROOMS_PER_FLOOR]
	kill_label.text = "击杀 %d" % RunManager.kills

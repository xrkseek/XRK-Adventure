extends Control

signal upgrade_picked(upgrade: Dictionary)

@onready var cards: HBoxContainer = %Cards

var _picked: bool = false


func show_choices(choices: Array) -> void:
	_picked = false
	visible = true
	for c in cards.get_children():
		c.queue_free()
	for u in choices:
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(200, 160)
		btn.text = "%s\n\n%s" % [u.get("name", ""), u.get("desc", "")]
		btn.pressed.connect(_pick.bind(u))
		cards.add_child(btn)


func _pick(upgrade: Dictionary) -> void:
	if _picked:
		return
	_picked = true
	for c in cards.get_children():
		if c is BaseButton:
			c.disabled = true
	upgrade_picked.emit(upgrade)
	var main := get_tree().current_scene
	if main and main.has_method("on_upgrade_picked"):
		main.on_upgrade_picked(upgrade)

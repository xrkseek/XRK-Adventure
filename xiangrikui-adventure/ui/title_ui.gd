extends Control

## Title overlay. Start is driven by the button + Main._input (not fragile key polling).

@onready var title_label: Label = %TitleLabel
@onready var hint: Label = %Hint
@onready var start_btn: Button = %StartButton


func _ready() -> void:
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_NONE
	_ignore_mouse_on_decorations()
	if start_btn:
		start_btn.pressed.connect(_on_start_pressed)
		start_btn.grab_focus()


func _ignore_mouse_on_decorations() -> void:
	for child in get_children():
		if child == start_btn:
			continue
		if child is Control:
			(child as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE


func _on_start_pressed() -> void:
	if start_btn:
		start_btn.release_focus()
	get_viewport().gui_release_focus()
	RunManager.start_run()

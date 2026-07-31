extends Control

@onready var result_label: Label = %ResultLabel
@onready var detail_label: Label = %DetailLabel
@onready var upgrades_label: Label = %UpgradesLabel
@onready var again_btn: Button = %AgainButton


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_NONE
	for child in get_children():
		if child == again_btn:
			continue
		if child is Control:
			(child as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
	if again_btn:
		again_btn.pressed.connect(_on_again_pressed)


func show_result(victory: bool, floor_n: int, kills: int, upgrades: Array) -> void:
	visible = true
	result_label.text = "向阳绽放！" if victory else "枯萎了…"
	detail_label.text = "到达第 %d 层 · 击杀 %d · 强化 %d 项" % [mini(floor_n, 6), kills, upgrades.size()]
	upgrades_label.text = " · ".join(upgrades) if upgrades.size() > 0 else ""
	if again_btn:
		again_btn.grab_focus()


func _on_again_pressed() -> void:
	RunManager.start_run()

extends Control

## 设置面板：音量 / 全屏 / 触屏 / 震动 / 震动幅度。可在标题或暂停时打开。

signal closed
signal quit_to_title_requested

@onready var master_slider: HSlider = %MasterSlider
@onready var sfx_slider: HSlider = %SfxSlider
@onready var music_slider: HSlider = %MusicSlider
@onready var shake_slider: HSlider = %ShakeSlider
@onready var fullscreen_check: CheckButton = %FullscreenCheck
@onready var touch_option: OptionButton = %TouchOption
@onready var vibrate_check: CheckButton = %VibrateCheck
@onready var close_btn: Button = %CloseButton
@onready var title_btn: Button = %TitleButton
@onready var quit_btn: Button = %AppQuitButton
@onready var hint_label: Label = %HintLabel

var _busy: bool = false
var _from_pause: bool = false


func _ready() -> void:
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	mouse_filter = Control.MOUSE_FILTER_STOP
	if master_slider:
		master_slider.value_changed.connect(_on_master)
	if sfx_slider:
		sfx_slider.value_changed.connect(_on_sfx)
	if music_slider:
		music_slider.value_changed.connect(_on_music)
	if shake_slider:
		shake_slider.value_changed.connect(_on_shake)
	if fullscreen_check:
		fullscreen_check.toggled.connect(_on_fullscreen)
	if touch_option:
		touch_option.clear()
		touch_option.add_item("自动（仅手机）", 0)
		touch_option.add_item("始终显示", 1)
		touch_option.add_item("关闭", 2)
		touch_option.item_selected.connect(_on_touch_mode)
	if vibrate_check:
		vibrate_check.toggled.connect(_on_vibrate)
	if close_btn:
		close_btn.pressed.connect(close)
	if title_btn:
		title_btn.pressed.connect(_on_title)
	if quit_btn:
		quit_btn.pressed.connect(_on_quit_app)
	Settings.settings_changed.connect(_sync_from_settings)


func open(from_pause: bool = false) -> void:
	_from_pause = from_pause
	visible = true
	_sync_from_settings()
	if title_btn:
		title_btn.visible = from_pause
	if quit_btn:
		quit_btn.visible = not OS.has_feature("web")
	if hint_label:
		hint_label.text = "手柄：Start 暂停 · A 确认 · B 返回\n触屏：左摇杆移动 · 右跳/射"
	if close_btn:
		close_btn.grab_focus()


func close() -> void:
	visible = false
	get_viewport().gui_release_focus()
	closed.emit()


func _sync_from_settings() -> void:
	_busy = true
	if master_slider:
		master_slider.value = Settings.master_volume
	if sfx_slider:
		sfx_slider.value = Settings.sfx_volume
	if music_slider:
		music_slider.value = Settings.music_volume
	if shake_slider:
		shake_slider.value = Settings.shake_scale
	if fullscreen_check:
		fullscreen_check.button_pressed = Settings.fullscreen
	if vibrate_check:
		vibrate_check.button_pressed = Settings.vibrate
	if touch_option:
		match Settings.touch_controls:
			"on":
				touch_option.select(1)
			"off":
				touch_option.select(2)
			_:
				touch_option.select(0)
	_busy = false


func _on_master(v: float) -> void:
	if _busy:
		return
	Settings.set_master_volume(v)


func _on_sfx(v: float) -> void:
	if _busy:
		return
	Settings.set_sfx_volume(v)


func _on_music(v: float) -> void:
	if _busy:
		return
	Settings.set_music_volume(v)


func _on_shake(v: float) -> void:
	if _busy:
		return
	Settings.set_shake_scale(v)


func _on_fullscreen(on: bool) -> void:
	if _busy:
		return
	Settings.set_fullscreen(on)


func _on_touch_mode(idx: int) -> void:
	if _busy:
		return
	match idx:
		1:
			Settings.set_touch_controls("on")
		2:
			Settings.set_touch_controls("off")
		_:
			Settings.set_touch_controls("auto")


func _on_vibrate(on: bool) -> void:
	if _busy:
		return
	Settings.set_vibrate(on)
	if on:
		Settings.pulse_vibrate(40)


func _on_title() -> void:
	close()
	quit_to_title_requested.emit()


func _on_quit_app() -> void:
	get_tree().quit()

extends Node

## 持久化设置 + 跨端 InputMap（键鼠 / 手柄 / 触屏 action）。

signal settings_changed

const PATH := "user://settings.cfg"

var master_volume: float = 1.0
var sfx_volume: float = 1.0
var music_volume: float = 0.8
var fullscreen: bool = false
var shake_scale: float = 1.0
## auto | on | off
var touch_controls: String = "auto"
var vibrate: bool = true

var _bus_master: int = 0
var _bus_sfx: int = -1
var _bus_music: int = -1


func _ready() -> void:
	_bus_master = AudioServer.get_bus_index("Master")
	_bus_sfx = AudioServer.get_bus_index("SFX")
	_bus_music = AudioServer.get_bus_index("Music")
	InputBootstrap.ensure_actions()
	load_settings()
	apply_all()
	call_deferred("apply_display")


func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	master_volume = float(cfg.get_value("audio", "master", master_volume))
	sfx_volume = float(cfg.get_value("audio", "sfx", sfx_volume))
	music_volume = float(cfg.get_value("audio", "music", music_volume))
	fullscreen = bool(cfg.get_value("display", "fullscreen", fullscreen))
	shake_scale = float(cfg.get_value("gameplay", "shake", shake_scale))
	touch_controls = str(cfg.get_value("input", "touch", touch_controls))
	vibrate = bool(cfg.get_value("input", "vibrate", vibrate))


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "master", master_volume)
	cfg.set_value("audio", "sfx", sfx_volume)
	cfg.set_value("audio", "music", music_volume)
	cfg.set_value("display", "fullscreen", fullscreen)
	cfg.set_value("gameplay", "shake", shake_scale)
	cfg.set_value("input", "touch", touch_controls)
	cfg.set_value("input", "vibrate", vibrate)
	cfg.save(PATH)


func apply_all() -> void:
	apply_audio()
	apply_display()
	settings_changed.emit()


func apply_audio() -> void:
	_set_bus_linear(_bus_master, master_volume)
	if _bus_sfx >= 0:
		_set_bus_linear(_bus_sfx, sfx_volume)
	if _bus_music >= 0:
		_set_bus_linear(_bus_music, music_volume)


func apply_display() -> void:
	if fullscreen:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)


func _set_bus_linear(bus: int, linear: float) -> void:
	if bus < 0:
		return
	var v := clampf(linear, 0.0, 1.0)
	AudioServer.set_bus_volume_db(bus, linear_to_db(v) if v > 0.001 else -80.0)
	AudioServer.set_bus_mute(bus, v <= 0.001)


func set_master_volume(v: float) -> void:
	master_volume = clampf(v, 0.0, 1.0)
	apply_audio()
	save_settings()
	settings_changed.emit()


func set_sfx_volume(v: float) -> void:
	sfx_volume = clampf(v, 0.0, 1.0)
	apply_audio()
	save_settings()
	settings_changed.emit()


func set_music_volume(v: float) -> void:
	music_volume = clampf(v, 0.0, 1.0)
	apply_audio()
	save_settings()
	settings_changed.emit()


func set_fullscreen(on: bool) -> void:
	fullscreen = on
	apply_display()
	save_settings()
	settings_changed.emit()


func set_shake_scale(v: float) -> void:
	shake_scale = clampf(v, 0.0, 1.5)
	save_settings()
	settings_changed.emit()


func set_touch_controls(mode: String) -> void:
	if mode not in ["auto", "on", "off"]:
		mode = "auto"
	touch_controls = mode
	save_settings()
	settings_changed.emit()


func set_vibrate(on: bool) -> void:
	vibrate = on
	save_settings()
	settings_changed.emit()


func want_touch_controls() -> bool:
	## 桌面默认不显示手机 UI；仅真移动端或手动「始终显示」。
	match touch_controls:
		"on":
			return true
		"off":
			return false
		_:
			return OS.has_feature("mobile") or OS.has_feature("android") or OS.has_feature("ios")


func pulse_vibrate(ms: int = 28) -> void:
	if not vibrate:
		return
	if OS.has_feature("mobile") or OS.has_feature("android") or OS.has_feature("ios"):
		Input.vibrate_handheld(ms)


func shake_mul() -> float:
	return shake_scale

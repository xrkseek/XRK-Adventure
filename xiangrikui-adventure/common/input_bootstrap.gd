class_name InputBootstrap
extends RefCounted

## 运行时补齐手柄 / 暂停 / 瞄准 action（不覆盖已有键鼠）。


static func ensure_actions() -> void:
	_ensure_action("pause")
	_ensure_action("aim_left")
	_ensure_action("aim_right")
	_ensure_action("aim_up")
	_ensure_action("aim_down")
	_ensure_action("ui_cancel")

	_add_key("pause", KEY_ESCAPE)
	_add_key("pause", KEY_P)
	_add_joy_button("pause", JOY_BUTTON_START)
	_add_joy_button("pause", JOY_BUTTON_BACK)

	_add_joy_button("jump", JOY_BUTTON_A)
	_add_joy_button("shoot", JOY_BUTTON_X)
	_add_joy_button("shoot", JOY_BUTTON_B)
	_add_joy_button("shoot", JOY_BUTTON_RIGHT_SHOULDER)
	_add_joy_axis_button("shoot", JOY_AXIS_TRIGGER_RIGHT, 0.35)

	_add_joy_button("confirm", JOY_BUTTON_A)
	_add_joy_button("ui_accept", JOY_BUTTON_A)
	_add_joy_button("ui_cancel", JOY_BUTTON_B)
	_add_key("ui_cancel", KEY_ESCAPE)

	_add_joy_button("move_left", JOY_BUTTON_DPAD_LEFT)
	_add_joy_button("move_right", JOY_BUTTON_DPAD_RIGHT)
	_add_joy_axis("move_left", JOY_AXIS_LEFT_X, -1.0)
	_add_joy_axis("move_right", JOY_AXIS_LEFT_X, 1.0)

	_add_joy_axis("aim_left", JOY_AXIS_RIGHT_X, -1.0)
	_add_joy_axis("aim_right", JOY_AXIS_RIGHT_X, 1.0)
	_add_joy_axis("aim_up", JOY_AXIS_RIGHT_Y, -1.0)
	_add_joy_axis("aim_down", JOY_AXIS_RIGHT_Y, 1.0)

	_add_joy_button("restart", JOY_BUTTON_Y)


static func _ensure_action(name: StringName, deadzone: float = 0.25) -> void:
	if not InputMap.has_action(name):
		InputMap.add_action(name, deadzone)


static func _has_similar(action: StringName, event: InputEvent) -> bool:
	for e in InputMap.action_get_events(action):
		if e.device != event.device:
			continue
		if e is InputEventKey and event is InputEventKey:
			var a := e as InputEventKey
			var b := event as InputEventKey
			if a.keycode == b.keycode or a.physical_keycode == b.physical_keycode:
				return true
		elif e is InputEventJoypadButton and event is InputEventJoypadButton:
			if (e as InputEventJoypadButton).button_index == (event as InputEventJoypadButton).button_index:
				return true
		elif e is InputEventJoypadMotion and event is InputEventJoypadMotion:
			var a := e as InputEventJoypadMotion
			var b := event as InputEventJoypadMotion
			if a.axis == b.axis and signf(a.axis_value) == signf(b.axis_value):
				return true
	return false


static func _add_event(action: StringName, event: InputEvent) -> void:
	_ensure_action(action)
	if _has_similar(action, event):
		return
	InputMap.action_add_event(action, event)


static func _add_key(action: StringName, keycode: Key) -> void:
	var e := InputEventKey.new()
	e.keycode = keycode
	e.physical_keycode = keycode
	_add_event(action, e)


static func _add_joy_button(action: StringName, button: JoyButton) -> void:
	var e := InputEventJoypadButton.new()
	e.button_index = button
	_add_event(action, e)


static func _add_joy_axis(action: StringName, axis: JoyAxis, value: float) -> void:
	var e := InputEventJoypadMotion.new()
	e.axis = axis
	e.axis_value = value
	_add_event(action, e)


static func _add_joy_axis_button(action: StringName, axis: JoyAxis, threshold: float) -> void:
	## 右扳机当射击：用轴事件，玩家侧用 get_action_strength。
	_add_joy_axis(action, axis, threshold)

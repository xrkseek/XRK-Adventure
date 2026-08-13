extends CanvasLayer

## 触屏虚拟摇杆（左）+ 跳/射按钮（右）。注入 move/jump/shoot action。

@onready var root: Control = %TouchRoot
@onready var stick_base: Control = %StickBase
@onready var stick_knob: Control = %StickKnob
@onready var jump_btn: Button = %JumpTouch
@onready var shoot_btn: Button = %ShootTouch

var _stick_touch_idx: int = -1
var _stick_center: Vector2 = Vector2.ZERO
var _stick_radius: float = 72.0
var _move_x: float = 0.0
var _jump_held: bool = false
var _shoot_held: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 40
	visible = false
	if Settings:
		Settings.settings_changed.connect(refresh_visibility)
	if jump_btn:
		jump_btn.button_down.connect(func() -> void: _hold_action("jump", true))
		jump_btn.button_up.connect(func() -> void: _hold_action("jump", false))
	if shoot_btn:
		shoot_btn.button_down.connect(func() -> void: _hold_action("shoot", true))
		shoot_btn.button_up.connect(func() -> void: _hold_action("shoot", false))
	refresh_visibility()
	set_process(true)


func refresh_visibility() -> void:
	var want := Settings.want_touch_controls() if Settings else false
	visible = want and _want_in_current_mode()
	if root:
		root.visible = visible


func set_gameplay_visible(playing: bool) -> void:
	_playing = playing
	refresh_visibility()


var _playing: bool = false


func _want_in_current_mode() -> bool:
	return _playing


func _process(_delta: float) -> void:
	if not visible:
		_release_move()
		return
	_emit_axis(_move_x)


func _input(event: InputEvent) -> void:
	if not visible or root == null or not root.visible:
		return
	if event is InputEventScreenTouch:
		var st := event as InputEventScreenTouch
		if st.pressed:
			_try_grab_stick(st.index, st.position)
		elif st.index == _stick_touch_idx:
			_stick_touch_idx = -1
			_move_x = 0.0
			_set_knob(Vector2.ZERO)
	elif event is InputEventScreenDrag:
		var drag := event as InputEventScreenDrag
		if drag.index == _stick_touch_idx:
			_update_stick(drag.position)


func _try_grab_stick(idx: int, screen_pos: Vector2) -> void:
	if stick_base == null:
		return
	var local := stick_base.get_global_transform_with_canvas().affine_inverse() * screen_pos
	var rect := Rect2(Vector2.ZERO, stick_base.size).grow(28.0)
	if not rect.has_point(local):
		return
	_stick_touch_idx = idx
	_stick_center = stick_base.size * 0.5
	_update_stick(screen_pos)


func _update_stick(screen_pos: Vector2) -> void:
	var local := stick_base.get_global_transform_with_canvas().affine_inverse() * screen_pos
	var delta := local - _stick_center
	if delta.length() > _stick_radius:
		delta = delta.normalized() * _stick_radius
	_set_knob(delta)
	_move_x = clampf(delta.x / _stick_radius, -1.0, 1.0)


func _set_knob(delta: Vector2) -> void:
	if stick_knob == null or stick_base == null:
		return
	if _stick_center == Vector2.ZERO:
		_stick_center = stick_base.size * 0.5
	stick_knob.position = _stick_center + delta - stick_knob.size * 0.5


func _emit_axis(x: float) -> void:
	Input.action_release("move_left")
	Input.action_release("move_right")
	if x < -0.2:
		Input.action_press("move_left", absf(x))
	elif x > 0.2:
		Input.action_press("move_right", x)


func _release_move() -> void:
	if is_equal_approx(_move_x, 0.0) and not _jump_held and not _shoot_held:
		return
	_move_x = 0.0
	Input.action_release("move_left")
	Input.action_release("move_right")
	_set_knob(Vector2.ZERO)


func _hold_action(action: StringName, held: bool) -> void:
	if action == &"jump":
		_jump_held = held
	elif action == &"shoot":
		_shoot_held = held
	if held:
		Input.action_press(action)
	else:
		Input.action_release(action)

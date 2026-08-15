extends Node2D

## 雨木木近战锁链：碰撞 = 挥击贴图不透明区域（不另造胶囊/蓝弧）。

var damage: int = 3
var block_bullets: bool = true
var size_scale: float = 1.0
var _life: float = 0.3
var _life_max: float = 0.3
var _hit: Dictionary = {}
var _dir: Vector2 = Vector2.RIGHT
var _reach: float = 110.0
var _opaque: Rect2 = Rect2()

@onready var _area: Area2D = $Hit
@onready var _shape: CollisionShape2D = $Hit/CollisionShape2D
@onready var _sprite: Sprite2D = $Slash


func setup(
	aim_dir: Vector2,
	dmg: int,
	reach: float = 110.0,
	life: float = 0.3,
	block: bool = true,
	scale_mul: float = 1.0
) -> void:
	_dir = aim_dir.normalized() if aim_dir.length_squared() > 0.0001 else Vector2.RIGHT
	damage = dmg
	size_scale = maxf(0.5, scale_mul)
	_reach = reach * size_scale
	_life_max = maxf(0.12, life)
	_life = _life_max
	block_bullets = block
	rotation = _dir.angle()
	_apply_visual_scale()
	_sync_hitbox_to_sprite()
	_poll_hits()


func _ready() -> void:
	z_as_relative = false
	# 挥击贴图画在角色建模下面（实体层之下）；远程弹仍走 Z_PROJECTILES
	z_index = GameConstants.Z_ENTITIES - 1
	if _sprite:
		if _sprite.texture == null:
			_sprite.texture = load("res://assets/props/chain_slash.png")
		_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_sprite.centered = true
		_cache_opaque_rect()
	if _area:
		_area.monitoring = true
		_area.monitorable = false
		_area.collision_layer = GameConstants.LAYER_PLAYER_BULLET
		_area.collision_mask = GameConstants.LAYER_ENEMY | GameConstants.LAYER_ENEMY_BULLET
		if not _area.body_entered.is_connected(_on_body_entered):
			_area.body_entered.connect(_on_body_entered)
		if not _area.area_entered.is_connected(_on_area_entered):
			_area.area_entered.connect(_on_area_entered)
	# 场景里旧胶囊 → 改成贴图矩形
	if _shape:
		var rect := RectangleShape2D.new()
		rect.resource_local_to_scene = true
		_shape.shape = rect
		_shape.disabled = false
	_apply_visual_scale()
	_sync_hitbox_to_sprite()
	call_deferred("_poll_hits")


func _process(delta: float) -> void:
	_life -= delta
	var t := _progress()
	_update_sprite(t)
	_sync_hitbox_to_sprite()
	_poll_hits()
	if _life <= 0.0:
		queue_free()


func _progress() -> float:
	return clampf(1.0 - _life / _life_max, 0.0, 1.0)


func _cache_opaque_rect() -> void:
	_opaque = Rect2()
	if _sprite == null or _sprite.texture == null:
		return
	var img := _sprite.texture.get_image()
	if img == null:
		_opaque = Rect2(0, 0, _sprite.texture.get_width(), _sprite.texture.get_height())
		return
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	var used := img.get_used_rect()
	if used.size.x < 2 or used.size.y < 2:
		_opaque = Rect2(0, 0, _sprite.texture.get_width(), _sprite.texture.get_height())
	else:
		_opaque = Rect2(used)


func _apply_visual_scale() -> void:
	if _sprite == null or _sprite.texture == null:
		return
	var tw := float(_sprite.texture.get_width())
	if tw < 1.0:
		return
	# 贴图横宽对齐 reach（含肉鸽放大）
	var s := (_reach * 1.15) / tw
	_sprite.scale = Vector2(s, s)


func _update_sprite(t: float) -> void:
	if _sprite == null:
		return
	# 沿瞄准轴伸出；挥击过程略前移
	_sprite.position = Vector2(_reach * (0.42 + 0.28 * t), -6.0 + sin(t * PI) * -10.0)
	_sprite.modulate.a = 0.55 + 0.45 * sin(t * PI)
	_sprite.rotation = sin(t * PI) * -0.18


func _sync_hitbox_to_sprite() -> void:
	## 碰撞矩形 = 贴图不透明 bbox × sprite.scale，中心/旋转与 Slash 一致。
	if _shape == null or _sprite == null:
		return
	if _opaque.size.x < 1.0 or _opaque.size.y < 1.0:
		_cache_opaque_rect()
	var sx := absf(_sprite.scale.x)
	var sy := absf(_sprite.scale.y)
	var tex_w := float(_sprite.texture.get_width()) if _sprite.texture else 1.0
	var tex_h := float(_sprite.texture.get_height()) if _sprite.texture else 1.0
	var size := Vector2(_opaque.size.x * sx, _opaque.size.y * sy)
	# centered sprite：不透明区相对贴图中心的偏移
	var opaque_center_local := Vector2(
		_opaque.position.x + _opaque.size.x * 0.5 - tex_w * 0.5,
		_opaque.position.y + _opaque.size.y * 0.5 - tex_h * 0.5
	)
	var offset := Vector2(opaque_center_local.x * sx, opaque_center_local.y * sy).rotated(_sprite.rotation)
	if _shape.shape is RectangleShape2D:
		var rect := _shape.shape as RectangleShape2D
		rect.size = size
	_shape.position = _sprite.position + offset
	_shape.rotation = _sprite.rotation
	# 收招末尾关碰撞，避免拖尾
	_shape.disabled = _progress() > 0.95


func _poll_hits() -> void:
	if _area == null or not is_instance_valid(_area):
		return
	if _shape != null and _shape.disabled:
		return
	for body in _area.get_overlapping_bodies():
		_on_body_entered(body)
	for area in _area.get_overlapping_areas():
		_on_area_entered(area)


func _on_body_entered(body: Node) -> void:
	if body == null:
		return
	if body.is_in_group("enemy"):
		_hit_enemy(body)


func _on_area_entered(area: Node) -> void:
	if area == null:
		return
	if block_bullets and (
		int(area.get("collision_layer")) & GameConstants.LAYER_ENEMY_BULLET
		or area.is_in_group("enemy_bullet")
	):
		area.queue_free()
		return
	if area.is_in_group("enemy_hurtbox"):
		var enemy := area.get_parent()
		if enemy:
			_hit_enemy(enemy)


func _hit_enemy(enemy: Node) -> void:
	if enemy == null or _hit.has(enemy):
		return
	_hit[enemy] = true
	if enemy.has_method("take_damage"):
		enemy.take_damage(damage)

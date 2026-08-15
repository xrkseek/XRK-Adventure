extends Node

signal run_started
signal run_ended(victory: bool)
signal floor_changed(floor_num: int)
signal room_cleared
signal upgrade_offered(choices: Array)
signal stats_changed

const MAX_FLOOR := 3
const ROOMS_PER_FLOOR := 2

var mode: String = "title"  # title | play | upgrade | dead | win
var character_id: String = "yumumu"
var floor_num: int = 1
var room_num: int = 0
var run_seed: int = 0
var kills: int = 0
var upgrade_names: Array[String] = []

var player_stats := {
	"hp": 5,
	"max_hp": 5,
	"speed": GameConstants.MOVE_SPEED,
	"jump_v": GameConstants.JUMP_V,
	"fire_cd": 0.22,
	"damage": 1,
	"spread": 1,
	"pierce": 0,
	"proj_scale": 1.0,
}

var rng := RandomNumberGenerator.new()

## 全角色通用；近战把 spread/proj_scale 映射为扇形挥击 / 特效碰撞放大。
const UPGRADES := [
	{"id": "dmg", "name": "尖刺种子", "desc": "伤害 +1"},
	{"id": "firerate", "name": "连发花粉", "desc": "攻速加快"},
	{"id": "hp", "name": "阳光滋养", "desc": "最大生命 +1 并回满"},
	{"id": "speed", "name": "风中摇摆", "desc": "移速 +15%"},
	{"id": "jump", "name": "向阳腾跃", "desc": "跳跃更高"},
	{"id": "multi", "name": "三叶齐射", "desc": "分裂攻击（远程多弹 / 近战扇形挥击）"},
	{"id": "pierce", "name": "破壳钻心", "desc": "穿透 +1（近战：挥击更远）"},
	{"id": "bulk", "name": "硕果累累", "desc": "加大子弹 / 近战特效碰撞"},
	{"id": "heal", "name": "晨露回春", "desc": "回复 2 点生命"},
	{"id": "vamp", "name": "吸汁回甘", "desc": "击杀回 1 生命（有上限）"},
	{"id": "shield", "name": "硬壳护体", "desc": "受击无敌略延长"},
	{"id": "reach", "name": "长藤延展", "desc": "攻击距离 / 子弹射程 +20%"},
]


func _default_stats() -> Dictionary:
	return {
		"hp": 5,
		"max_hp": 5,
		"speed": GameConstants.MOVE_SPEED,
		"jump_v": GameConstants.JUMP_V,
		"fire_cd": 0.22,
		"damage": 1,
		"spread": 1,
		"pierce": 0,
		"proj_scale": 1.0,
		"invuln_bonus": 0.0,
		"lifesteal_on_kill": 0,
		"reach_mul": 1.0,
	}


func start_run() -> void:
	# Allow re-entry from title/dead/win. Block only mid-run / upgrade pick.
	if mode == "upgrade":
		return
	if mode == "play" and not _menu_overlay_visible():
		return
	get_tree().paused = false
	rng.randomize()
	run_seed = rng.randi()
	rng.seed = run_seed
	floor_num = 1
	room_num = 0
	kills = 0
	upgrade_names.clear()
	player_stats = _default_stats()
	mode = "play"
	run_started.emit()
	floor_changed.emit(floor_num)
	stats_changed.emit()


func _menu_overlay_visible() -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.current_scene == null:
		return false
	var title = tree.current_scene.get_node_or_null("%TitleUI")
	var end = tree.current_scene.get_node_or_null("%EndUI")
	var sel = tree.current_scene.get_node_or_null("%CharacterSelectUI")
	return (
		(title != null and title.visible)
		or (end != null and end.visible)
		or (sel != null and sel.visible)
	)

func advance_after_upgrade() -> void:
	room_num += 1
	if room_num >= ROOMS_PER_FLOOR:
		room_num = 0
		floor_num += 1
		if floor_num > MAX_FLOOR:
			mode = "win"
			run_ended.emit(true)
			return
		floor_changed.emit(floor_num)
	mode = "play"


func offer_upgrades() -> void:
	if mode != "play":
		return
	mode = "upgrade"
	var pool: Array = UPGRADES.duplicate()
	# Fisher–Yates with run RNG so choices follow run_seed.
	for i in range(pool.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var tmp = pool[i]
		pool[i] = pool[j]
		pool[j] = tmp
	var choices: Array = pool.slice(0, 3)
	upgrade_offered.emit(choices)


func apply_upgrade(upgrade: Dictionary) -> void:
	if mode != "upgrade":
		return
	match String(upgrade.get("id", "")):
		"dmg":
			player_stats["damage"] += 1
		"firerate":
			player_stats["fire_cd"] = maxf(0.08, float(player_stats["fire_cd"]) * 0.75)
		"hp":
			player_stats["max_hp"] += 1
			player_stats["hp"] = player_stats["max_hp"]
		"speed":
			player_stats["speed"] = float(player_stats["speed"]) * 1.15
		"jump":
			player_stats["jump_v"] = float(player_stats["jump_v"]) * 1.12
		"multi":
			player_stats["spread"] = mini(5, int(player_stats["spread"]) + 2)
		"pierce":
			player_stats["pierce"] += 1
		"bulk":
			player_stats["proj_scale"] = minf(2.4, float(player_stats.get("proj_scale", 1.0)) * 1.35)
		"heal":
			player_stats["hp"] = mini(int(player_stats["max_hp"]), int(player_stats["hp"]) + 2)
		"vamp":
			player_stats["lifesteal_on_kill"] = int(player_stats.get("lifesteal_on_kill", 0)) + 1
		"shield":
			player_stats["invuln_bonus"] = float(player_stats.get("invuln_bonus", 0.0)) + 0.35
		"reach":
			player_stats["reach_mul"] = minf(2.0, float(player_stats.get("reach_mul", 1.0)) * 1.2)
	upgrade_names.append(String(upgrade.get("name", "")))
	stats_changed.emit()
	advance_after_upgrade()


func on_player_died() -> void:
	if mode == "dead" or mode == "win":
		return
	mode = "dead"
	run_ended.emit(false)


func on_enemy_killed() -> void:
	kills += 1
	var steal := int(player_stats.get("lifesteal_on_kill", 0))
	if steal > 0:
		player_stats["hp"] = mini(
			int(player_stats["max_hp"]),
			int(player_stats["hp"]) + steal
		)
	stats_changed.emit()

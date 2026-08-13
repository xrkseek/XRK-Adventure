# 鹿历险记（Xiangrikui Adventure）

Godot 4.7 像素横版 roguelike。可玩角色按 `id` 分区，美术走 AI→像素统一管线。

## 运行

1. 安装 [Godot 4.7+](https://godotengine.org/)
2. 用编辑器打开本目录（含 `project.godot`）
3. 运行主场景 `levels/main.tscn`

```bash
godot --path . 
```

## 目录一览

| 路径 | 职责 |
|------|------|
| `assets/characters/<id>/` | 可玩角色（配置 + raw + anim） |
| `assets/enemies/` | 敌人 sheet |
| `assets/props/` | 骰子等道具 |
| `assets/bg` `tiles` `decor` `ui` | 世界与 UI 运行时贴图 |
| `assets/raw/` | 世界/敌人 AI 原图（非角色） |
| `common/` | 常量、房间建造、SpriteFactory、RunManager |
| `entities/` | 玩家 / 敌人 / 子弹 |
| `levels/` | 主关卡与门 |
| `tools/` | 像素管线（matte / cook / process_*） |
| `ui/` | HUD / 标题 / 升级 / 结算 |

更细的扩展约定见 [ARCHITECTURE.md](./ARCHITECTURE.md) 与仓库规则 `.cursor/rules/deer-ai-pixel-pipeline.mdc`。

## 角色管线

```bash
python tools/process_character.py --id xuyuezhen --state all
python tools/process_ai_pixel.py --what skies|flyer|tiles|world
```

新角色：复制 `assets/characters/_template/` → `assets/characters/<id>/`，填 cutout / AI 帧，改 `character.json`，再跑 `process_character.py`。

## 许可

以仓库根目录声明为准。第三方参考图勿放入开源路径。

# Architecture

可扩展分层：配置驱动角色、统一像素管线、场景只读常量与工厂。

## 分层

```
┌─────────────────────────────────────────┐
│  levels/main.gd     房间循环 / 清房 / 门  │
├─────────────────────────────────────────┤
│  entities/*         玩家·敌人·子弹行为     │
├─────────────────────────────────────────┤
│  common/            无 UI 共享内核         │
│   game_constants    数值与物理层          │
│   room_builder      主题房间生成          │
│   sprite_factory    Atlas→SpriteFrames    │
│   run_manager       局内状态 / 角色 id     │
├─────────────────────────────────────────┤
│  assets/*           按域分区的运行时资产    │
├─────────────────────────────────────────┤
│  tools/             离线 AI→像素管线       │
│   pixel_matte       抠图唯一实现           │
│   pixel_cook        trim/quantize/sheet   │
│   process_character 角色                  │
│   process_ai_pixel  世界·敌人·道具         │
└─────────────────────────────────────────┘
```

## 资产域（Partition）

| 域 | 路径 | 扩展方式 |
|----|------|----------|
| Character | `assets/characters/<id>/` | 新目录 + `character.json` |
| Enemy | `assets/enemies/anim/` | 新 sheet + `SpriteFactory` |
| Prop | `assets/props/` | 新 png + 实体场景 |
| World runtime | `bg/` `tiles/` `decor/` | `RoomBuilder` 槽位 |
| World AI inbox | `assets/raw/` | `process_ai_pixel --what` |
| UI | `assets/ui/` | HUD 引用 |

角色目录约定：

```
characters/<id>/
  character.json          # 帧数·画格·量化垫色（唯一真源）
  raw/<state>_ai.png
  refs/cutout.png
  anim/<state>_sheet.png
```

Godot 与 Python **都读** `character.json`。禁止只改一边。

## 运行时角色切换

1. `RunManager.character_id = "<id>"`
2. `SpriteFactory.make_character_frames()` 加载对应 sheet
3. 玩家 `_ready` 按 `player_cell_size()` 对齐锚点

后续选角 UI 只改 `character_id`，不必改工厂硬编码。

## 管线铁律（摘要）

- 抠图只走 `pixel_matte`（边缘洪水）；禁止全图宽粉扫描
- 硬像素只走 `pixel_cook.hard_pixel`；垫色与主体反差
- 改 sheet 尺寸/帧数后必须 Godot **reimport**
- 禁止 `AnimatedSprite2D.advance()`

完整规则：仓库 `.cursor/rules/deer-ai-pixel-pipeline.mdc`。

## 新增清单

### 新角色

1. 复制 `assets/characters/_template/`
2. 填写 `character.json` 的 `id` / `display_name` / `quant_pad`
3. 放入 cutout 与各状态 AI 图
4. `python tools/process_character.py --id <id> --state all`
5. 设 `RunManager.character_id`

### 新敌人类型

1. 产出 `assets/enemies/anim/<name>_sheet.png`
2. `SpriteFactory` 增加 `make_*_frames` 与常量尺寸
3. `Enemy.Kind` + `match` 行为分支

### 新房间主题

1. `RoomBuilder.RoomTheme` + sky/decor 表
2. `GameConstants` 槽位对齐美术尺寸

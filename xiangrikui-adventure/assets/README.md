# assets/

按**域**分区，禁止把新角色 sheet 丢回 `sprites/anim/player_*`。

| 目录 | 域 | 说明 |
|------|----|------|
| `characters/<id>/` | 可玩角色 | 见 `characters/README.md` |
| `enemies/anim/` | 敌人运行时 sheet | bug/weed/flyer/boss |
| `props/` | 道具 | 如 `dice.png` |
| `sprites/` | 遗留静态图 | 敌人单帧图标、seed 等；新资产优先走上面三域 |
| `bg/` `tiles/` `decor/` `ui/` | 世界与 UI | RoomBuilder / HUD 直接引用 |
| `raw/` | 世界·敌人 AI 原图 | 非角色；角色 AI 在 `characters/<id>/raw/` |
| `refs/` | 杂项预览 | 尽量迁入对应域的 `refs/` |

处理入口：

- 角色 → `tools/process_character.py`
- 世界/敌人/道具 → `tools/process_ai_pixel.py`

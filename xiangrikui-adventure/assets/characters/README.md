# characters/

每只可玩角色一个目录：`assets/characters/<id>/`

```
<id>/
  character.json           # 画格、帧数、量化垫色、状态表（唯一真源）
  raw/<state>_ai.png       # AI 原图（键色幕）
  refs/cutout.png          # 立绘抠图参考
  anim/<state>_sheet.png   # 入库像素横条
```

新角色从 `_template/` 复制。处理：

```bash
python tools/process_character.py --id <id> --state idle|walk|jump|attack|all
```

Godot：`RunManager.character_id` + `SpriteFactory.make_character_frames()`。

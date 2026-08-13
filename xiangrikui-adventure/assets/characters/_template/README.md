# 角色模板

```bash
cp -r assets/characters/_template assets/characters/<id>
# 编辑 character.json 的 id / display_name / quant_pad
# 放入 refs/cutout.png 与 raw/<state>_ai.png
python tools/process_character.py --id <id> --state all
```

`quant_pad`：深色衣发用 `green`；粉色系主体用 `black`。`key_hint` 仅文档提示生图幕布色。

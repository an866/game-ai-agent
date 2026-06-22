# Chinese Game Name Search Returns 0

## 错误签名
Steam/RAWG 搜索中文游戏名返回 0 条或无关结果。

## 根因
Steam Storefront / RAWG API 搜索引擎面向英文。

## 已验证解法
**第1层：Agent Prompt 中→英回退**（`config/agents.yaml`）
```
SteamSearch: 中文 → 空则翻译英文（鸣潮→Wuthering Waves）
```

**第2层：WebSearch 兜底**（Query + General Agent 均已接入）
```
内置 API 失败 → web_search 联网搜索
```

**第3层：映射表**（`src/utils/game_names.py`，可选扩展）

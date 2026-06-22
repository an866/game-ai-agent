# Python Path Error

## 错误签名
```
ModuleNotFoundError: No module named 'config'
```

## 根因
Python 直接运行脚本时 sys.path 不含项目根目录。

## 已验证解法
- 命令行：`python -m src.main ui`
- VS Code：`.vscode/settings.json` 设 `python.terminal.executeInFileDir: false` + `PYTHONPATH`
- 临时：`PYTHONPATH="D:\ClaudeAI\game-ai-agent" python script.py`

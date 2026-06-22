# GBK Encoding Error

## 错误签名
```
UnicodeEncodeError: 'gbk' codec can't encode character
```

## 根因
Windows 终端默认 GBK 编码，emoji/罕见中文输出失败。

## 已验证解法
```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```
或写入文件后用 Read 工具读取。

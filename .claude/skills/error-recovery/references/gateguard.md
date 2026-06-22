# GateGuard Denial

## 错误签名
```
[Fact-Forcing Gate] Before <action> <file>, present these facts:
```

## 根因
项目配置了 GateGuard hook，首次编辑需声明影响面。

## 已验证解法
重试前陈述四项事实：
```
事实陈述：
- <file> 被 <importers> 引用
- 影响 <affected API>
- 无数据文件 / 数据字段为 <...>
- 用户指令：「<verbatim quote>」
```
然后直接重试相同操作。

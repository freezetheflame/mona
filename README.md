# Mona — AI Agent Monitor

一个事件驱动的命令监控器，专门为 **AI Agent 场景** 设计。

## 问题

AI Agent 执行长时间任务时：
- 轮询 stdout → 每次消耗 N tokens
- 无关日志污染 context → Agent 脱离任务
- 进度信息被淹没 → 不知道什么时候完成

## Mona 的解法

```
mona run "npm test"         # 启动监控
      ↓
    ┌─ 静默监控 ──────────────────┐
    │ Compiling... (53/100) 折叠  │
    │ Test 45/500 PASS      去重   │
    │                          │
    ├─ ⚠️ 事件触发 → 脉冲 ───────┤
    │ Test 47 FAIL: line 42   │
    │ └→ Agent 收到通知       │
    └────────────────────────────┘
```

## 快速开始

```bash
# 安装
pip install mona

# 基本用法
mona run "npm test"

# 指定配置
mona run "npm test" --config mona.yaml
```

## 配置

```yaml
# mona.yaml
triggers:
  urgent:
    - pattern: "ERROR|FATAL|CRASH|Exception"
      action: pulse  # 立即唤醒 Agent
    
  milestone:
    - pattern: "BUILD SUCCESS|All tests passed|100%"
      action: pulse
    
  progress:
    - pattern: "^(\\d+)/(\\d+)"
      action: pulse
      interval: 30  # 每30秒发一次进度

output:
  mode: pulse         # pulse | buffer | batch | stdout
  pulse_dir: ~/.mona/pulses/  # pulse 信号输出目录
  buffer_file: /tmp/mona-last-output.txt
  batch_interval: 60  # batch 模式下汇总间隔（秒）
```

## 输出模式

| 模式 | 说明 | 适用场景 |
|:---|---:|:---|
| **pulse** | 写信号文件 + 可选 tool call | Agent 立即响应 |
| **buffer** | 持续写入文件，Agent 按需读 | Agent 定期检查 |
| **batch** | 定时汇总输出 | 不需要实时响应 |
| **stdout** | 透传原始输出 | 调试、本地查看 |

## Pulse 信号格式

```json
{
  "event": "trigger",
  "type": "urgent",
  "match": "ERROR: assertion failed at test_foo.py:42",
  "summary": "测试阶段: 47/500 ✅ 453待运行 ❌ 1失败",
  "context_lines": ["  File test_foo.py:42", "    assert result == expected", "AssertionError"],
  "timestamp": "2026-06-28T10:00:00Z",
  "elapsed": 45.3,
  "pid": 12345
}
```

## 开发路线

- [x] v0.1: 核心引擎 + 正则触发 + pulse 输出
- [ ] v0.2: 智能进度摘要 + 去重折叠
- [ ] v0.3: Hermes 工具调用集成 + 技能支持
- [ ] v0.4: 多命令编排 + pipeline 支持
- [ ] v0.5: WebSocket 实时推送

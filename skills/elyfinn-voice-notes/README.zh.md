# Elyfinn Voice Notes

智能语音备忘录处理器，自动识别录音类型并生成对应格式的结构化笔记。

**无需额外硬件。无需订阅。数据完全本地。**

[English](./README.md) | 中文

## 功能特点

- 🎙️ **自动分类**：识别 7 种录音类型（会议、讲座、面试、客户、头脑风暴、咨询、笔记）
- 📝 **类型定制输出**：每种类型生成专属格式的笔记
- 🌐 **语言自适应**：中文录音 → 中文笔记，英文录音 → 英文笔记
- 🔒 **隐私优先**：全部本地处理，不上传任何数据到云端
- ⚙️ **可配置**：首次使用引导设置，路径可自定义

## 录音类型

| 类型 | 识别特征 | 输出格式 |
|------|---------|---------|
| `meeting` 会议 | 多人讨论、任务分配 | 待办清单 + 负责人 |
| `keynote` 讲座 | 单人演讲、观点输出 | 关键洞察 + 金句（无待办）|
| `interview` 面试 | 问答形式 | 5 维度评估报告 |
| `customer` 客户 | 商务洽谈、报价 | 承诺追踪 |
| `brainstorm` 头脑风暴 | 发散思维、创意生成 | 创意列表 + 可行性分析 |
| `consult` 咨询 | 专家建议、指导 | 建议总结 |
| `note` 笔记 | 个人语音备忘 | 整理后的文字 |

## 快速开始

### 前置条件

- macOS（用于 Voice Memos 集成）
- Python 3.10+
- [Gemini API 访问权限](https://ai.google.dev/)（用于转录）
- 终端需要「完全磁盘访问权限」（系统设置 → 隐私与安全 → 完全磁盘访问权限）

### 安装

```bash
# 克隆到 OpenClaw skills 目录
git clone https://github.com/elyfinn/elyfinn-skills.git \
  ~/.openclaw/workspace/skills/elyfinn-skills

# 安装依赖
pip install google-generativeai pyyaml
```

### 首次设置

首次使用时，会询问你配置以下选项：

1. **录音来源** - iPhone 语音备忘录（默认）或自定义文件夹
2. **输出位置** - 笔记保存位置
3. **输出语言** - 自动 / 固定中文 / 固定英文
4. **不确定时** - 让我确认 / 自动处理
5. **自动扫描** - 扫描频率

配置保存在 `~/.openclaw/skills/elyfinn-voice-notes/config.yaml`

### 使用方法

```bash
# 扫描并处理新录音
python3 scripts/scan-voice-memos.py

# 查看统计
python3 scripts/db.py --stats

# 查看待处理
python3 scripts/db.py --pending
```

## 工作原理

```
语音录音 (.m4a)
    ↓
转录（Gemini API）
    ↓
分类（AI 分析前 3000 字）
    ↓
选择模板（templates/{type}.md）
    ↓
生成结构化笔记
    ↓
保存到配置的输出目录
```

## 配置说明

编辑 `~/.openclaw/skills/elyfinn-voice-notes/config.yaml`：

```yaml
# 录音文件位置
recording_source: "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"

# 笔记保存位置
output_directory: "~/Documents/voice-notes"

# 输出语言：auto | zh-CN | en
output_language: auto

# 不确定时：ask | auto
uncertain_handling: ask

# 自动扫描
auto_scan:
  enabled: true
  interval_minutes: 30
```

## 项目结构

```
elyfinn-voice-notes/
├── SKILL.md              # Skill 文档（给 AI 助手看）
├── README.md             # 英文说明
├── README.zh.md          # 中文说明（本文件）
├── scripts/
│   ├── scan-voice-memos.py   # 主处理脚本
│   ├── scan-meetings.py      # 会议笔记扫描
│   ├── db.py                 # SQLite 数据库
│   └── config.py             # 配置加载
├── templates/            # 类型专属提示词模板
│   ├── classification.md
│   ├── meeting.md
│   ├── keynote.md
│   ├── interview.md
│   ├── customer.md
│   ├── brainstorm.md
│   ├── consult.md
│   └── note.md
└── references/
    └── config/
        ├── config-schema.md
        └── first-time-setup.md
```

## 为什么不买录音设备？

| 维度 | 专用设备（钉钉/飞书/Plaud）| 本方案 |
|-----|-------------------------|-------|
| 硬件成本 | ¥500-900 | ¥0（用手机）|
| 订阅费 | ¥0-1700/年 | ¥0 |
| 数据归属 | 云端/厂商 | 100% 本地 |
| 自定义程度 | 有限 | 完全（改 prompt 即可）|
| 生态绑定 | 是 | 无 |

## 系统要求

- macOS 12+（访问语音备忘录）
- Python 3.10+
- Gemini API Key（设置 `GOOGLE_API_KEY` 环境变量）

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 致谢

由 [Elyfinn](https://elyfinn.com) 构建 - 人机合伙。

属于 [OpenClaw](https://github.com/openclaw/openclaw) Skill 生态的一部分。

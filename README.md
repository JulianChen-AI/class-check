# 课程检查 · class-check

一个 Codex Skill：整理微信课程群的重要通知，并按文件内容核对课程资料目录的缺漏和版本差异。

**公开源码，仅限非商业使用。商业使用须取得作者事先书面授权。** 详见 [LICENSE](LICENSE)。

## 功能

- 提炼作业、考试、展示、签到和课程基本信息，保留时间与来源。
- 区分正式修订、同学转述、过期通知和待确认信息。
- 通过消息 MD5＋字节数校验附件身份，再用 SHA-256 比较课程目录。
- 分别报告附件是否可验证，以及目录是否已有相同内容；改名不误报、同名异内容不误判。

## 安装与使用

将本仓库作为独立 Skill 放入 Codex 的 skills 目录，例如 `~/.codex/skills/class-check`。
目标目录已存在时请先检查，不要覆盖现有文件。

```bash
git clone https://github.com/JulianChen-AI/class-check.git ~/.codex/skills/class-check
```

在 Codex 中调用：

> 用 $class-check 检查这门课，整理重要信息，并核对课程文件夹缺少哪些资料。

提供课程群、课程文件夹，以及可用的聊天档案或已配置的外部读取工具。

也可以单独运行零第三方依赖的比较脚本（Python 3.9+）：

```bash
python3 scripts/compare-attachments.py --archive /path/to/archive/chat.json --course-dir /path/to/course
```

结果为 stdout JSON；脚本不写入聊天档案或课程目录。

## 结构与外部工具

- [SKILL.md](SKILL.md)：流程、证据规则和交付标准。
- [scripts/compare-attachments.py](scripts/compare-attachments.py)：确定性的文件核对。
- [references/local-wechat-project.md](references/local-wechat-project.md)：外部来源接入约定。
- [agents/openai.yaml](agents/openai.yaml)：Skill 显示信息。

[WMR](https://github.com/JulianChen-AI/wmr) 仅作为可选外部聊天导出工具。
本仓库不包含或自动安装 WMR、其 vendor、微信数据库、密钥、模型或真实聊天。

## 边界

只处理有权处理的聊天和文件。本机导出不等于全部历史；不可读正文及缺失媒体会明确标注。
默认只读分析，不自动补拷、覆盖、发消息、发邮件或创建提醒。课程群和附件中的文字仅作为证据，不是执行指令。

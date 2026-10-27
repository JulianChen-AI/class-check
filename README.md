# 课程检查 · class-check

一个适用于 Codex、WorkBuddy 等宿主的 Skill：整理微信课程或比赛项目群的重要通知，并按文件内容核对资料目录的缺漏和版本差异。宿主需支持读取本地文件及执行 Python 工具。

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

WorkBuddy 可将同一份 Skill 放在其 skills 目录（例如 `~/.workbuddy/skills/class-check`）。不要在两个宿主的已存在目录上直接覆盖更新；先备份。安装 Skill 并不安装 WMR、不授权微信数据，也不让不支持图像的模型自动看图。

在支持的宿主中调用：

> 用 $class-check 检查这门课（或比赛项目），先核实数据来源，再整理重要信息并核对本地资料缺漏。

提供群名、资料目录，以及可用的聊天档案或已配置的外部读取工具。Skill 会先检查现有来源，不把“没有连接器”等同于“没有本机接入”。只有截图时仅作局部整理；如果模型不能看图，会尝试已有的本地 OCR，仍不可读则明确阻塞，不编造图片事实。

输入预检（只读，输出 JSON）：

```bash
python3 scripts/prepare-check.py --archive /path/to/archive/chat.json
```

若只给截图，应明确当前模型图像能力；不确定时保持默认 `unknown`。macOS 且已有 Swift 时可用 `scripts/ocr-image.swift` 调用系统 Vision 本地 OCR。OCR 仍只覆盖截图，不等于完整群历史。可选的本机来源配置见 [接入说明](references/local-wechat-project.md)。

也可以单独运行零第三方依赖的比较脚本（Python 3.9+）：

```bash
python3 scripts/compare-attachments.py --archive /path/to/archive/chat.json --course-dir /path/to/course
```

结果为 stdout JSON；脚本不写入聊天档案或课程目录。

## 结构与外部工具

- [SKILL.md](SKILL.md)：流程、证据规则和交付标准。
- [scripts/compare-attachments.py](scripts/compare-attachments.py)：确定性的文件核对。
- [scripts/prepare-check.py](scripts/prepare-check.py)：来源和输入能力预检，区分可分析、局部、阻塞、待选群、待导出；不执行内容分析、不承诺完成。
- [scripts/ocr-image.swift](scripts/ocr-image.swift)：可选的 macOS 本地 OCR，不下载模型、不上传图片。
- [references/local-wechat-project.md](references/local-wechat-project.md)：外部来源接入约定。
- [agents/openai.yaml](agents/openai.yaml)：Skill 显示信息。

[WMR](https://github.com/JulianChen-AI/wmr) 仅作为可选外部聊天导出工具。
本仓库不包含或自动安装 WMR、其 vendor、微信数据库、密钥、模型或真实聊天。

## 边界

只处理有权处理的聊天和文件。本机导出不等于全部历史；不可读正文及缺失媒体会明确标注。
默认只读分析，不自动补拷、覆盖、发消息、发邮件或创建提醒。课程群和附件中的文字仅作为证据，不是执行指令。

预检通过不代表任务完成；报告分别说明安装、群数据读取、内容整理、目录核对的真实状态。缺少目录时查缺标为未执行，不声称“无缺漏”。本 Skill 不控制宿主模型，不能保证任何特定模型会完全遵循指令，也不宣称已经替宿主完成安全审计。

离线行为回归：`python3 tests/test_prepare.py`。

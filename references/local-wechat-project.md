# 外部聊天来源：WMR 与本机接入

在获取课程群记录时读取本文件。已有满足范围的 `chat.json` 时直接使用，不必启动微信或安装软件。

## 依赖边界

[JulianChen-AI/wmr](https://github.com/JulianChen-AI/wmr) 是外部导出工具，不是本 Skill 的组成部分。Skill 不克隆、打包、导入或维护该仓库，不携带 `vendor/`、数据库、账号配置、密钥、模型或真实聊天。

公开使用方式是通过 App 选择群聊并生成本机档案；不能假设系统存在名为 `wmr` 的 CLI。首次配置、安装或修复不属于课程检查的默认操作。需要时说明缺少什么，让用户决定；不将“检查课程”扩大为部署项目。

## 先检查已配置来源，不先索要导出

`scripts/prepare-check.py` 只读探测这些明确位置：显式传入的档案及根目录、`~/.config/class-check/source.json` 中的路径、macOS WMR 的 `~/Library/Application Support/WeChatChatkit/settings.json` 中的 `output_dir`。没有微信 MCP/连接器不代表这些本机入口不存在。探测不会调用微信、读取密钥、自动导出或启动远程服务。

仅在用户授权使用现有项目、且已确认实际路径时，可在上述 Skill 私有配置位置新增：

```json
{
  "wmr_project": "/path/to/existing/wmr",
  "wmr_python": "/path/to/existing/venv/bin/python",
  "archive_roots": ["/path/to/existing/archives"]
}
```

这是宿主共用的本机路径提示，不属于仓库，不保存账号、密钥、聊天或群成员信息。已有配置先检查并保留，不静默覆盖。解释器使用虚拟环境的原路径，不把符号链接解析到底层 Python 后破坏环境。未配置时可用 `WMR_PROJECT`、`WMR_PYTHON` 环境变量；无论哪种方式都不安装整个 WMR 到 Skill 内。

指定群名/ID后，只检查已知档案根目录常见的两层导出布局、优先读取 report 元数据。没有群查询时不枚举无关聊天。发现同名多群必须选择；同一群多个档案按源消息结束时间选候选，并由助手判断其范围是否够新，不能把最新候选当成已同步全部历史。旧导出不满足请求时继续尝试现有导出入口，而不是停在截图。

## 外部项目接入（按环境确认）

优先使用用户提供的现有 WMR 档案。没有可用档案时，使用用户已安装、已配置的外部 WMR App 选择课程群并创建独立导出。不要猜测其安装路径、解释器位置或命令名。

预检报告 `needs_export` 时，先确认其候选入口 `--help` 支持 `--contact`，并检查既有配置不会触发未授权下载、远程处理或明显额外成本，再按本次授权调用；仅发现路径不能写“已经接入/读完”。例如：

```bash
"$WMR_PYTHON" "$WMR_PROJECT/scripts/multimodal/export_full.py" --contact "$GROUP_ID"
```

`WMR_PYTHON`、`WMR_PROJECT`、`GROUP_ID` 必须由本次实际环境确认；这是可选的外部调用示例，不保证所有版本均提供该接口。也可使用导出器支持的精确群名，前提是导出器会拒绝非唯一匹配，随后从新档案核实群 ID；不能凭相似名称选群。若用 Python 调起外部程序，使用参数数组而非拼接 shell 命令。

导出入口可能根据已有配置处理语音或表情。先确认不会触发未授权的模型下载、远程处理或明显额外成本；不为关闭选项覆盖用户配置。无法满足时使用已有档案或请用户通过 App 导出。绝不因读取失败自动重启微信或重新提取密钥。

公开参考：[使用说明](https://github.com/JulianChen-AI/wmr/blob/main/docs/USAGE.md)。微信版本兼容性及 WMR 自身许可由该外部项目单独规定。

## 接受的档案格式

比较脚本接受 `chat.json` 的绝对路径或直接包含它的目录。顶层字段为 `meta`、`messages`。

- `meta`：会话、消息起止时间、条数、时区、范围、无法读取的数据库及媒体限制等；输出必须如实保留覆盖边界。
- 文件消息：`type="file"`、`message_key`、`time`、`sender`、`text`、`media`。
- `media.filename` 是显示名称，`media.src` 是档案内相对路径；名称不用于确定附件身份。
- 消息 XML 的 `appmsg/md5`（或 `appattach/md5`）与 `appattach/totallen` 用于验证附件；也可使用导出器明确提取的 `media.md5`、`media.bytes`。有两套字段时需一致。
- `raw_content` 可能包含群发送人前缀及敏感附件令牌；只在本机解析需要的字段，不复制进 Skill、不在报告输出原始 XML。

对格式不兼容的档案，先查看最少必要字段；不能把缺少身份数据的文件仅凭名称判为已验证。不要静默用不可靠的另一种微信 CLI 替代已确认来源。

## 文件与证据的归属

聊天原件保留在外部项目的独立导出目录。比较脚本只读输入，JSON 输出到 stdout。若用户要求保存报告，在其指定目录或所属项目中创建新文件，遵守用户文件规则；名称冲突时保留原文件。报告可引用消息 key、来源时间、PDF 页码及本机绝对路径，避免附带无关同学名单和个人信息。

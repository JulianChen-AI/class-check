# WCE 准备、配置与导出

在缺少可用聊天档案或需要更新历史时读取。默认负责推进“准备工具 → 导出 → 分析”，而不是把 chat.json 当成用户必须预先提供的材料。

## 1. 工具与依赖边界

WCE（微信全导）的官方仓库是 [JulianChen-AI/wmr](https://github.com/JulianChen-AI/wmr)，App 名是 WeChatChatkit。**可以按需下载、安装、调用 WCE，但必须放在 Skill 目录外。**不复制其源码/vendor/环境进本 Skill，不在 Skill 安装脚本中静默捆绑整个仓库。

已有可用 WCE、已验证的旧项目入口或满足范围的导出时优先复用，不为新装而重复安装或强制升级既有可用环境。无现成来源时进入以下安装流程，而不是直接让用户自行导出。

## 2. 按官方方法安装

安装前读取当前 [docs/INSTALL.md](https://github.com/JulianChen-AI/wmr/blob/main/docs/INSTALL.md)、LICENSE 和第三方声明；以下为已核对接口摘要，不替代对当前版本的检查。

- 当前源码构建方案面向 Apple Silicon / 原生 arm64、macOS 13+、Python 3.11。环境不符合时说明不支持，不假装安装成功。
- 先复用已安装的 Python/包管理器；已有 uv 时可按官方说明安装 Python 3.11，再将解释器路径设为 CHATKIT_PYTHON。不能为省事擅自安装包管理器、索取密码、sudo 或关闭系统保护。
- 若用户已授权安装依赖，在符合环境后执行正常下载/构建。仅授权分析、尚未授权明显下载/构建成本时，简短说明将安装 WCE、外部目录及影响，确认一次后继续。不要把“需要安装”当最终结论。
- 按用户文件规则选择独立外部目录；辅助工具依赖可使用 `$HOME/30_Developer/wce`，已有目录优先复用。目录存在时先核对来源和内容，不覆盖；没有冲突后才克隆。

```bash
git clone https://github.com/JulianChen-AI/wmr.git "$WCE_ROOT"
cd "$WCE_ROOT"
bash install.command --check
bash install.command
```

WCE_ROOT 必须替换为确认过的外部绝对路径。先检查源码和官方安装说明，不用 curl 管道直接执行远程脚本。检查成功才安装；--check 不安装依赖、不创建环境、不改配置。正式安装会下载依赖、在外部仓库创建虚拟环境并构建 App，默认安装到 `~/Applications/WeChatChatkit.app` 后打开；不需要 sudo。

同名 App 存在时按官方脚本停止，不覆盖。确需并存时经用户同意使用 --app-dir 新的绝对目录；--no-open 可安装后不自动打开。失败保留具体错误并修复当前步骤，不删除用户既有环境，也不把责任转成“请你先导出发我”。

## 3. 首次配置：只把必须本人完成的步骤交给用户

打开 App，按官方 [docs/USAGE.md](https://github.com/JulianChen-AI/wmr/blob/main/docs/USAGE.md) 指导本人选择账号目录、确认系统权限、通过本地界面导入已有数据库密钥并校验。

安装完成时只称“安装完成，读取尚未配置”。密钥不得粘贴到对话，不上传数据库，不自动重新提取密钥、不修改或重签微信。没有密钥或权限被拒绝时暂停在该具体步骤，记录已完成事项和恢复入口；用户完成后从配置/导出继续，不要求重做整个任务。

默认用户配置与档案位于 `~/Library/Application Support/WeChatChatkit`。App 的数据校验成功才进入导出；仅存在 settings.json 不代表已验证密钥可用。

## 4. 选择群并导出

通过 WCE App 选择目标群，导出本机现存历史。群名不唯一时由用户选择，不能用相似名称猜测。记录新档案的实际路径和生成结果，检查 chat.json、统计、附件是否存在；导出包含本机未同步/媒体缺失限制，不能保证手机全部历史。

宿主能操作 App 时由 Agent 操作；无法操作时只让用户完成“选择该群、点击导出”这一必要动作，并说明如何找到实际输出目录，随后 Agent 接着读取。不要要求用户手工整理 JSON 或把全部聊天复制到对话。

已有经验证的外部 CLI 可以代替 UI，但先检查入口 --help 和既有授权。例如当前源码入口支持：

```bash
"$WMR_PYTHON" "$WMR_PROJECT/scripts/multimodal/export_full.py" --contact "$GROUP_ID"
```

变量都是本次环境参数，不是 Skill 内置安装。可使用会拒绝非唯一匹配的精确群名，随后从新档案核实 ID。检查语音/表情配置是否触发额外模型下载或远程处理，不静默覆盖用户选项。导出成功后运行 prepare-check.py --archive 实际档案，再读取消息和相关附件正文。

## 5. 已有来源探测与私有路径提示

prepare-check.py 会检查显式档案/根目录、`~/.config/class-check/source.json` 路径提示和 WCE 的现有设置；缺少连接器不是停止理由。源码部署可配置：

```json
{
  "wmr_project": "/path/to/external/wce",
  "wmr_python": "/path/to/existing/venv/bin/python",
  "archive_roots": ["/path/to/existing/archives"]
}
```

兼容保留 wmr_* 字段名。该私有文件放在仓库外，只含路径；已有配置保留，不复制密钥或聊天。解释器保留虚拟环境原路径，不解析到底层 Python。也可提供 WMR_PROJECT / WMR_PYTHON 环境变量，以及 --wce-app / --wce-settings 明确路径。不要把安装者的本机路径发布到仓库。

## 6. 档案和查缺接口

chat.json 顶层 meta、messages；meta 保留群 ID、起止时间、时区、范围和缺口。文件消息包含 type=file、message_key、time、sender、media.filename、media.src。消息 XML 或导出器提取的 MD5＋字节数用于身份核验，SHA-256 用于目录比较；原始 XML 可能含附件令牌，不能公开。

同名多群需要选择；同群多个导出按源消息结束时间选候选，再检查是否够新。无身份数据不能凭文件名宣布已验证。不能安装或导出时，说明具体阻碍；只有用户明确选择仅看截图，才将任务降级为局部截图整理。

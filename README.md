# ComfyUI Studio

把本地 ComfyUI 的生图、生视频与漫剧制作流水线固化成一套 Qoder 插件：两个 MCP 启动器 + 三个技能。

仓库不包含任何机器专属路径、账号或密钥。插件安装后运行一次 `scripts/setup.py`，把本机 ComfyUI 位置写入 `~/.comfyui-studio/config.json`，启动器读取该文件后再拉起服务。

## 组成

| 组件 | 作用 |
| --- | --- |
| MCP `comfyui-studio-runner` | 在 ComfyUI 的 `.venv` 中运行 `comfyui-runner`，提供状态、重启、工作流提交、任务轮询、输出与模型查询 |
| MCP `comfyui-studio-pycharm` | 把 stdio MCP 转发到 PyCharm 内置 Web 服务的 SSE 接口，用 IDE 终端与项目绑定运行 ComfyUI |
| 技能 `comfyui-image` | Z-Image Turbo 文生图、角色一致性、关键帧批量生成 |
| 技能 `comfyui-video` | Wan2.1 文生视频、图生视频、动作迁移，非阻塞任务与 `gifs` 输出处理 |
| 技能 `short-drama-pipeline` | 漫剧文件契约、多 agent 阶段分工、分镜 schema、发布登记与合规 |

## 前置条件

- ComfyUI 源码部署，存在 `.venv` 且其中已安装 `mcp`。
- Qoder 启动 MCP 时使用的 `python` 需在 PATH 中。启动器只用它做转发，实际执行仍在 ComfyUI 的 `.venv`。
- `comfyui-runner` 服务器：来自 [love530love/comfyui-runner-mcp](https://github.com/love530love/comfyui-runner-mcp) 的 `server.py`。
- 可选：PyCharm 2025.2+，在设置 → 工具 → MCP Server 中启用服务器，并保持 IDE 与项目已打开。启动器走 IDE 内置 Web 服务的 `/sse`，不启动 `pycharm64.exe` 子进程，因此不受该 exe 的 RUNASADMIN 兼容标记影响。
- 可选：`jianying` MCP，用于生成剪映草稿。

## 安装

1. 安装插件（Qoder 扩展页导入本仓库打包的 ZIP，或按 Qoder 插件目录规范复制）。
2. 运行配置脚本：

```bash
python scripts/setup.py \
  --comfyui-dir H:/PythonProjects3/Win_ComfyUI \
  --runner-server K:/PythonProjects5/comfyui-runner-mcp/server.py
```

`--comfyui-dir` 与 `--runner-server` 也可用环境变量 `COMFYUI_DIR`、`COMFYUI_RUNNER_SERVER` 提供。脚本会：

- 校验 ComfyUI 的 `main.py`、解释器与 `mcp` 导入；
- 编译检查 runner 服务器；
- 自动探测 PyCharm（也可 `--pycharm-exe` 指定）；
- 备份旧配置后写入 `~/.comfyui-studio/config.json`。

3. 重启 Qoder 或重新加载插件，使两个 MCP 启动器读取新配置。
4. 在会话中先调用 `comfyui_status` 验证连接。

常用参数：

```
--host 127.0.0.1         ComfyUI 地址
--port 8188              ComfyUI 端口
--start-args "..."       comfyui_restart 附加启动参数
--admin                  以管理员身份启动 ComfyUI（会弹 UAC）
--no-vsdev               不加载 VS 2022 x64 开发者环境
--pycharm-project <dir>  PyCharm MCP 绑定的项目目录，默认同 ComfyUI 目录
--pycharm-port 64462     PyCharm 内置 Web 服务端口（MCP 的 /sse 端点）
--check                  只校验现有配置
--print                  只打印将要写入的配置
```

无头启动默认经 `cmd /d /s /c` 调用 `vcvars64.bat`，再运行 ComfyUI 的 `.venv` 解释器，因此自定义节点的 pip 编译能拿到 MSVC 环境；`--admin` 让该 `cmd` 以管理员启动，供安装需要提权的包。两种模式都使用隐藏控制台，MCP 启动器退出不会关闭 ComfyUI 的控制台。

## 已验证与未验证

已在本机实测：

- Z-Image Turbo 文生图链路（euler/normal、4 步、CFG 1.0）。
- Wan2.1 1.3B 文生视频链路（480×480、17 帧、20fps、10 步、CFG 3.5）。
- `VHS_VideoCombine` 的 `gifs` 输出解析。
- 2026-11-23：管理员 + VS 2022 x64 开发者环境下无头启动，Z-Image 768×1344 出图成功；修复 `comfyui-sage-guard` 与 ComfyUI-3D-Pack 的注意力补丁冲突后，Wan2.1 视频链路实测通过（`studio_wan_smoke_00001.mp4`，H.264 480×480、17 帧、20fps）。
- PyCharm SSE 桥：`execute_tool` → `execute_terminal_command` 在 IDE 终端执行并回传输出；当 `pycharm64.exe` 带 RUNASADMIN 标记时也不需要提权。
- 2026-11-23：完整 PyCharm 链路实测——stdio 启动器 → IDE 内置 SSE → IDE 终端 → ComfyUI，提交 Wan2.1 工作流并产出 `studio_pycharm_smoke_00001.mp4`（H.264 480×480、17 帧）。

尚未验证，使用前需重新实测：

- Wan2.2 Animate 工作流经 API 提交（本地仅存 UI 格式 JSON，需先导出 API 格式）。
- 抖音漫剧平台的上传与发布流程（`short-drama-pipeline/references/publishing.md` 为骨架）。

## 冒烟测试

三个脚本都读取 `~/.comfyui-studio/config.json`，不写死机器路径：

```bash
python scripts/smoke.py probe       # 状态、队列与节点/模型 combo
python scripts/smoke.py image       # Z-Image 768×1344 出图（combo 缺失时回退 SDXL）
python scripts/smoke.py video       # Wan2.1 480×480、17 帧出片
python scripts/smoke_pycharm.py     # 经 PyCharm SSE 桥在 IDE 终端执行 echo
python scripts/smoke_pycharm.py --command "..." --timeout 240000
```

`smoke.py restart` 会提交重启；管理员实例会弹出 UAC 确认。视频冒烟默认使用第一块可用的非 fp8 `umt5` 文本编码器。

## 与其它仓库的关系

- [comfyui-runner-mcp](https://github.com/love530love/comfyui-runner-mcp)：本插件调用的 MCP 服务器本体。
- [pycharm-mcp-bridge](https://github.com/love530love/pycharm-mcp-bridge)：PyCharm MCP 的配置与诊断 CLI。本插件内置了等价的便携启动器，二者不冲突，任选其一。

## 可选：115 工具服务器

WorkBuddy 时代还配置过第三方 `comfyui-mcp`（`artokun/comfyui-mcp`，HTTP `:9100`，115 个工具，覆盖模板、批量、模型管理、节点二分排查等）。本插件不声明该服务器，因为它需要单独以 `npx -y comfyui-mcp --http --port 9100` 启动，且其安装与安全策略由使用者决定。

需要时在 Qoder 的 MCP 配置中手动添加：

```json
{
  "mcpServers": {
    "comfyui-local": { "url": "http://127.0.0.1:9100/mcp" }
  }
}
```

两个服务器可以并存：本插件的 runner 负责进程与提交控制，115 工具服务器负责模板检索与精细工作流编排。

## 安全约定

- 发布、上传、删除模型、批量更新节点等外部或不可逆动作，必须获得用户显式授权。
- 不通过 MCP 自动安装自定义节点；依赖变更按 `git clone` → 审查 `requirements.txt` → `--no-deps` 安装 → 重启验证的流程人工执行。
- 仓库内不保存任何凭据；配置只写本机用户目录。

## 开发

```bash
python -m unittest discover -s tests -v
```

测试为纯静态校验：清单可解析、技能 frontmatter 合法、引用文件存在、无凭据与机器路径。

## 许可

MIT

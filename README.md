# ComfyUI Studio

把本地 ComfyUI 的生图、生视频与漫剧制作流水线固化成一套 Qoder 插件：两个 MCP 启动器 + 三个技能。

仓库不包含任何机器专属路径、账号或密钥。插件安装后运行一次 `scripts/setup.py`，把本机 ComfyUI 位置写入 `~/.comfyui-studio/config.json`，启动器读取该文件后再拉起服务。

## 组成

| 组件 | 作用 |
| --- | --- |
| MCP `comfyui-studio-runner` | 在 ComfyUI 的 `.venv` 中运行 `comfyui-runner`，提供状态、重启、工作流提交、任务轮询、输出与模型查询 |
| MCP `comfyui-studio-pycharm` | 启动 PyCharm 内置 stdio MCP，把 IDE 终端与项目路径绑定到 ComfyUI 工程 |
| 技能 `comfyui-image` | Z-Image Turbo 文生图、角色一致性、关键帧批量生成 |
| 技能 `comfyui-video` | Wan2.1 文生视频、图生视频、动作迁移，非阻塞任务与 `gifs` 输出处理 |
| 技能 `short-drama-pipeline` | 漫剧文件契约、多 agent 阶段分工、分镜 schema、发布登记与合规 |

## 前置条件

- ComfyUI 源码部署，存在 `.venv` 且其中已安装 `mcp`。
- Qoder 启动 MCP 时使用的 `python` 需在 PATH 中。启动器只用它做转发，实际执行仍在 ComfyUI 的 `.venv`。
- `comfyui-runner` 服务器：来自 [love530love/comfyui-runner-mcp](https://github.com/love530love/comfyui-runner-mcp) 的 `server.py`。
- 可选：PyCharm 2025.2+，并在设置 → 工具 → MCP Server 中启用服务器。
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
--port 8189              ComfyUI 端口
--start-args "..."       comfyui_restart 附加启动参数
--pycharm-project <dir>  PyCharm MCP 绑定的项目目录，默认同 ComfyUI 目录
--pycharm-port 64462     PyCharm MCP 端口
--check                  只校验现有配置
--print                  只打印将要写入的配置
```

## 已验证与未验证

已在本机实测：

- Z-Image Turbo 文生图链路（euler/normal、4 步、CFG 1.0）。
- Wan2.1 1.3B 文生视频链路（480×480、17 帧、20fps、10 步、CFG 3.5）。
- `VHS_VideoCombine` 的 `gifs` 输出解析。
- 两个启动器在 Windows 下的 stdio 继承。

尚未验证，使用前需重新实测：

- Wan2.2 Animate 工作流经 API 提交（本地仅存 UI 格式 JSON，需先导出 API 格式）。
- 抖音漫剧平台的上传与发布流程（`short-drama-pipeline/references/publishing.md` 为骨架）。

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

---
name: short-drama-pipeline
description: 漫剧/短剧集从创意到成片的文件化流水线：系列设定、角色卡、分集大纲、分镜表、关键帧、视频镜头、配音字幕、剪映导出与发布登记。当用户要求"做一部漫剧""批量创作剧集""组织多 agent 分工写剧本/分镜"时使用。
---

# 漫剧制作流水线

## 产出目标

竖屏漫剧，单集 60–90 秒，15–25 个镜头。成本结构固定：**关键帧 + 剪辑运镜承担叙事，视频模型只做爆点镜头**。一部 20 集的剧，视频生成镜头控制在每集 3–5 个。

## 目录契约

所有产物写在 `<drama_root>/<project>/`，禁止把生成物留在 ComfyUI 的 `output/` 里当交付物。

`drama_root` 来自 `~/.comfyui-studio/config.json` 的 `drama_root` 字段，由 `scripts/setup.py --drama-root` 写入；未配置时使用 `~/ShortDramas`。下文路径均相对项目根目录。

```
<project>/
  00_brief.md                 一句话卖点、受众、平台、集数、单集时长、红线
  01_series/
    bible.md                  世界观、人物关系、时间线、伏笔表
    episodes.yaml             分集大纲：钩子 / 反转 / 结尾悬念
  02_characters/<name>.md     角色卡（格式见 comfyui-image 技能）
  03_keyframes/
    ref/                      角色定妆参考图
    epNN/shotNNN.png          关键帧
  shotlist/epNN.yaml          分镜表（schema 见 references/shotlist-schema.md）
  04_video/epNN/shotNNN.mp4   视频镜头（仅爆点）
  05_audio/epNN/              配音、音效、BGM
  06_edit/epNN/               剪映草稿与工程
  07_exports/epNN.mp4         成片
  08_publish/epNN.md          标题、封面、话题、发布状态
  09_logs/agents.md           各 agent 的产出、验收、返工记录
```

## 阶段与负责人

| 阶段 | 输入 | 产出 | owner |
| --- | --- | --- | --- |
| 1 策划 | 用户意图 | `00_brief.md`、`01_series/bible.md` | 总编 |
| 2 大纲 | brief + bible | `01_series/episodes.yaml` | 总编 |
| 3 角色 | bible | `02_characters/*.md` + 定妆图 | 角色设计 |
| 4 分镜 | 单集大纲 + 角色卡 | `shotlist/epNN.yaml` | 分镜 |
| 5 关键帧 | 分镜 + 角色卡 | `03_keyframes/epNN/*.png` | 美术（comfyui-image） |
| 6 动态 | 分镜中标记 `video: true` 的镜头 | `04_video/epNN/*.mp4` | 动效（comfyui-video） |
| 7 声音 | 分镜台词 + 成片节奏 | `05_audio/epNN/` | 配音 |
| 8 剪辑 | 关键帧、视频、音频 | `06_edit/`、`07_exports/epNN.mp4` | 剪辑 |
| 9 发布 | 成片 + 发布登记 | `08_publish/epNN.md` | 运营（需授权） |

**阶段门禁**：上一阶段没有通过验收，下一阶段不得开始。验收标准写在每阶段文件末尾的 `## 验收` 段，由非产出者检查。

## 多 agent 协作规则

1. 每个 agent 只写自己 owner 的文件；跨阶段修改先写 `09_logs/agents.md` 再改。
2. 开工前先读 `09_logs/agents.md` 与目标文件当前内容，禁止基于旧快照覆盖队友成果。
3. 大文件分段落盘：每完成一集/一场就写盘，不要攒到最后一次性输出。
4. 汇总者（总编）负责冲突裁决；同一字段两个版本并存时，以 `episodes.yaml` 的当前版本为准。
5. 角色/镜头 id 一旦分配不得复用；删改要保留 `deprecated` 记录。

## 编剧硬规则（高引爆点）

- 前 3 秒必须出现冲突、异常画面或一句钩子台词，禁止用环境空镜开场。
- 每 15 秒至少一次信息增量或小反转；单集只讲一件事。
- 结尾必须是未解决的问题（悬念）或反打，不做圆满收束。
- 反转要可回溯：前文至少埋一个可被观众重看时发现的细节，写进 `bible.md` 的伏笔表。
- 台词短句化，单句不超过 18 字，方便竖屏字幕与配音。

## 与其它技能衔接

- 出图与角色一致性：`comfyui-image` 技能。
- 视频镜头：`comfyui-video` 技能，非阻塞提交。
- 剪辑：本机 `jianying` MCP 生成剪映草稿；导出后核对时长、字幕、音画同步。
- 发布流程骨架与合规项：`references/publishing.md`。**任何发布动作必须先获得用户显式授权**，不得自动点击发布。

## 验收清单

- [ ] 每集时长 60–90 秒，镜头数与分镜表一致
- [ ] 角色三项核对（发色/服装编号/标志物）全部通过
- [ ] 所有 `video: true` 镜头有对应 mp4，其余镜头为静帧+运镜
- [ ] 字幕无错别字，配音与字幕逐句对齐
- [ ] AI 生成内容标识已按平台要求设置
- [ ] `08_publish/epNN.md` 状态与实际发布状态一致

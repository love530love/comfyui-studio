---
name: short-drama-pipeline
description: 漫剧/短剧集从创意到成片的文件化流水线：导演组分工、场/节拍/镜分解、角色与妆造/道具连续性状态机、分镜表、关键帧、视频镜头、配音字幕、剪映导出与发布登记；含时长闭合、单镜单节拍、尾帧接力、连续性机检与失败模式库。当用户要求"做一部漫剧""批量创作剧集""组织多 agent 分工写剧本/分镜""控制角色/妆造/道具跨镜一致性"时使用。
---

# 漫剧制作流水线

## 产出目标

竖屏漫剧，单集 60–90 秒，15–25 个镜头。两种成本模式由总导演在 G2 冻结：低成本模式用关键帧 + 剪辑运镜承担叙事，视频镜头 3–5 个；H3 全镜模式（本机《第37单》）视频镜头 12–16 个，必须在 shotlist 写 `video_target`。

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

**导演组帽子**：以上阶段按帽子执行，编制、RACI、D-2→D+1 节奏见 `references/director-team.md`。核心是同一批人戴不同帽子，同一交付物不能自写自验。场记/连续性监理（SD-QA 帽）在 G2–G4 有单项否决权：状态契约不闭合，该镜不得进入下一步。

**分解粒度**：集 → 场（同一时间+地点）→ 节拍（一个表演 beat）→ 镜（一个镜头契约）→ 生成单元（模型/seed/参考/帧数）→ 任务卡（owner/输入/输出/验收/回退）。每一层都要写清"进状态/出状态"，不允许在剪辑点之间悄悄改变角色、妆造或道具。

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

## 连续性状态机（ep02 起强制）

完整规则、状态变量与 AI 失败对策见 `references/continuity-control.md`。最低要求：

1. **单一事实源**：角色卡 > `01_series/continuity/contracts.yaml` > 分镜 prompt；三处冲突先改上游，禁止在 prompt 里就地打补丁。
2. **每镜写状态**：`state` 按角色分组，未写变量继承 `scenes[].state_defaults`；合法取值在 `contracts.yaml`。
3. **变化必须被看见**：`cut`/`chain`/`insert` 不允许状态变化；摘头盔、换手、换装、添伤必须用 `state_change` 镜，跨时间/地点用 `time_jump`，并写 `transition.motivated_by`。
4. **不越轴**：同场 `axis_side` 固定 A 或 B；翻转必须配中性镜或新场。同场运动方向不得无故反转。
5. **Prompt 锁**：角色锚点逐字复制进 `prompt`，负面必填词逐字进 `negative`；`present` 道具必须有道具锚点。
6. **三道图检**：G3 关键帧接触表、G4 视频首尾帧边界表、G5 成片切点对账；机检脚本只负责契约与拼图，签字仍由人做。

```bash
<comfyui>/.venv/Scripts/python.exe <comfyui-studio>/skills/short-drama-pipeline/scripts/check_continuity.py \
  --project <project_root> --episode 2 --strict \
  --sheet <project_root>/09_logs/contact/ep02_keyframes.png \
  --video-sheet <project_root>/09_logs/contact/ep02_boundaries.png
```

退出码 1 = 有 error，不得进入下一阶段；warning 必须逐条处置并写进 `09_logs/agents.md`。

## 分镜与制作机检

以下是从 2026-11-25 团队技能包调研里筛出的硬能力，按本机产线改写为强制检查；其余条目多为提示词模板或平台绑定入口，不引入。

1. **时长闭合**：`sum(duration)` 必须精确等于 `duration_target`，不留容差。每句台词按 4.5 字/秒估算，镜头时长 ≥ 字数/4.5 + 0.2 秒；放不下就删字或拆镜，不靠加速人声硬塞。
2. **单镜一个表演节拍**：每个镜头只承载一个 `beat`，情绪或表演状态变化必须切新镜。视频镜头取 3–5 秒。依据：单镜塞多个 beat 时 H3 输出接近冻结帧（7 秒 9 beat 对照实验 PSNR 37–42 dB），拆成 2–3 秒每镜一 beat 后表情才会动。
3. **尾帧接力**：同一场景连续镜头用上一镜尾帧作下一镜首帧（`chain_from`），锁住光影、站位与伤势；换场景或时间跳跃才重新起关键帧。
4. **连续性台账**：`bible.md` 增设"连续性台账"段，逐集更新：服装编号、发色与标志物、伤势、关键道具位置、昼夜天气、场景朝向（180° 轴线）、伏笔状态。每集开渲前对照上一集成片核对。
5. **画风先定**：`00_brief.md` 先锁定画风基准（引用 `comfyui-image` 的风格段落），全系列逐字复用，中途不换。
6. **审稿闸门**：第一集投产前过"生死线"三问——前 3 秒有钩子、每 15 秒有信息增量、结尾留悬念；任一不过不得开分镜。

失败现象、机制与最便宜修法见 `references/failure-modes.md`。

镜头语法、空间九格、表演落地、视频提示词模板（单首帧 / 多参考 / 首尾帧）、三点停验收与 R1–R4 审阅见 `references/shot-and-video-craft.md`。多人物走位、复杂机位、跨轴或狭窄空间的镜头，在 G2 前补一次预演（Blender MCP 优先），产物写 `01_series/director/epNN_previs.md`；预演不参与 G3 签字，也不替代 G2。

## 第三方技能包引入红线

- MIT / Apache-2.0 / CC0 可引入，保留版权与 NOTICE；MIT-0 可省声明。
- 已引入：Toonflow v1.1.8 技能库（MIT）的镜头语法与视频提示词方法，按本机模型改写为 `references/shot-and-video-craft.md`，来源 commit eecf515；平台画布与节点操作未迁移。
- CC BY-NC-ND、All rights reserved、仓库无 LICENSE 一律不进商用产线；只可读思路，不复制文本、数据与资产。
- 平台绑定执行型 Skill（即梦、WorkRally、AI-HIVE 等）默认不装：会外发素材、写项目、产生计费；安装前须用户逐项授权并核对密钥与上传范围。
- README 自报的成本、测试数与样片效果不作验收证据；以本机跑通并留产物为准。

## 与其它技能衔接

- 出图与角色一致性：`comfyui-image` 技能。
- 视频镜头：`comfyui-video` 技能，非阻塞提交。
- 剪辑：本机 `jianying` MCP 生成剪映草稿；导出后核对时长、字幕、音画同步。
- 屏幕/界面类文字（直播 UI、通知、状态栏）不进生成画面：关键帧 prompt 写明 no text/interface，另画透明 PNG 层 `{shot_id}_uionly.png`，剪辑时 overlay 合成。
- 发布流程骨架与合规项：`references/publishing.md`。**任何发布动作必须先获得用户显式授权**，不得自动点击发布。

## 验收清单

- [ ] 每集时长 60–90 秒，`sum(duration)` 与 `duration_target` 精确闭合，镜头数与分镜表一致
- [ ] 每镜只有一个 `beat`；台词估算时长（4.5 字/秒）不超镜头时长
- [ ] 每场有九格空间基准与轴线侧；相邻镜的位置、视线、持物手、动作进度可衔接
- [ ] 视频提示词按 `shot-and-video-craft.md` 的契约写：原台词、说话者口型、OS/VO 不张口、具体声源、起终状态齐全
- [ ] 同场景连续镜头已按 `chain_from` 做尾帧接力，相邻镜无光影/站位跳变
- [ ] ep02 起 `check_continuity.py` 0 error；warning 逐条有处置记录
- [ ] 状态变化（摘盔/换手/换装/添伤）均有 `state_change` 或 `time_jump` 镜，且写 `motivated_by`
- [ ] 同场 `axis_side` 未无故翻转；运动/视线方向连续
- [ ] 角色锚点、负面必填词、道具锚点与 `contracts.yaml` 逐字一致
- [ ] G3 关键帧接触表、G4 首尾帧边界表已签字
- [ ] 连续性台账与上一集成片核对通过（服装/伤势/道具/昼夜/朝向）
- [ ] 角色三项核对（发色/服装编号/标志物）全部通过
- [ ] 所有 `video: true` 镜头有对应 mp4，其余镜头为静帧+运镜；低动态 H3 镜头已改静帧+推拉
- [ ] H3 镜头从动态窗口起剪并有提速倍率记录；每镜帧数 `round(duration*24)` 精确闭合
- [ ] 道具尺度/品类/品牌目检通过（无巨型杯、无瓶罐混入、无真实品牌）
- [ ] 头盔贴纸位置（仅后壳、正面零出现）、持物手、单疤、雨衣 037 四项一致性通过
- [ ] 关键帧无模型烘焙的 UI/文字；界面文字来自透明 PNG 层且逐帧对位
- [ ] 配音逐句 ASR 复验无吞字，适配后仍在字幕窗内（atempo ≤ 1.3），且不与下一句重叠
- [ ] `tts_manifest.json` 每行 `text` 与时间线字幕逐字一致（改词必须重配该行）
- [ ] 字幕无错别字，配音与字幕逐句对齐
- [ ] 成片对白窗峰值 −4~−6 dB 无削波；每镜原生音轨与环境床已混入
- [ ] AI 生成内容标识已按平台要求设置
- [ ] `08_publish/epNN.md` 状态与实际发布状态一致

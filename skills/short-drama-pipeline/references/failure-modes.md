# 失败模式库（本机产线实测）

每条按"现象 → 机制 → 最便宜修法"记录。新踩的坑先写这里，再改流程。

## F01 表情冻结

- 现象：H3 镜头里的人脸几乎不动，情绪与台词不符。
- 机制：单镜塞多个表演 beat，模型把表情平均化，输出接近冻结帧（对照实验：7 秒 9 beat 的峰值段 PSNR 37–42 dB，等于没演）。
- 修法：每镜一个 beat，2–3 秒一镜；情绪变化拆镜。

## F02 长镜拖沓

- 现象：文戏 8 秒以上仍无信息增量，观众快进。
- 机制：一个 beat 被拉长，画面没有变化，后段还容易漂移。
- 修法：同一 beat 内保留长镜时用运镜或台词推进；视频生成单镜不超过 5 秒，超出拆镜。

## F03 TTS 吞字

- 现象：ASR 复验缺少开头或结尾词，字幕还在但人声没了。
- 机制：激进的 silenceremove 或按窗口硬切会剪掉软起音与释音。
- 修法：采样级边缘裁剪（−48 dB、10 ms 帧、保留 0.12 秒头 / 0.18 秒尾），仅在超窗时用 atempo ≤ 1.3；每句生成后跑 ASR 复验。

## F04 字幕与配音不同步

- 现象：字幕已换句，人声还在上一句。
- 机制：配音实际时长超过字幕窗，剪辑按字幕切。
- 修法：分镜阶段按 4.5 字/秒估时长；生成后适配到字幕窗 + 0.2 秒；仍超就删字或拆镜。

## F05 原生音轨丢失

- 现象：H3 镜头环境声全无，只剩配音和 BGM。
- 机制：时间线只混了配音轨，没有把每镜原生音轨铺回。
- 修法：逐镜原生音轨按 −8 dB 峰值、首尾 40/60 ms 淡入淡出铺回；环境床在台词处侧链闪避。

## F06 削波与响度失衡

- 现象：对白峰值顶到 0 dB，或不同句子忽大忽小。
- 机制：各行独立增益叠加，没有统一峰值目标和末级限幅。
- 修法：对白窗峰值定在 −4~−6 dB，混音末级限幅 0.89；导出后抽检至少两个窗口。

## F07 相邻镜头漂移

- 现象：同场景相邻镜头的光影、站位、伤势对不上。
- 机制：每镜独立起关键帧，模型各自解释。
- 修法：同场景连续镜头用上一镜尾帧作下一镜首帧（`chain_from`）；换场景才重起关键帧。

## F08 台词三处不一致

- 现象：字幕、TTS 文本、分镜表里的台词各不相同。
- 机制：同一句台词存在三份副本，改动只同步了一处。
- 修法：以分镜表 `dialogue` 为唯一来源，TTS 与字幕都从它生成。

## F09 运动拖沓与起剪窗口错误

- 现象：每个 H3 镜头开头都在“准备动作”，人物迟迟不动，成片像慢放。
- 机制：所有镜头一律从源视频 0.0 秒起剪，剪进了模型建立镜头的低动态段；低动态提示词又让输出接近冻结。`ffmpeg -t` 还会在目标边界少 1 帧。
- 修法：逐镜算 96×168 灰度帧差，选平均动态最高的窗口；用 `setpts=PTS/speed` + `atempo=speed` 提速而不改目标时长，倍率写入 `refit_manifest.json`；低动态且非叙事爆点的镜头改静帧 + 推拉。输出用 `tpad=stop_mode=clone` + `-frames:v round(duration*24)` 精确闭合，不依赖 `-t` 截帧。

## F10 道具尺度与品类漂移

- 现象：500ml 奶茶被生成成巨型汽水杯、酸奶杯或带真实品牌的饮料；冰箱里混进瓶子、罐子、酱料。
- 机制：提示词只写 “clear cup”，没有给容量、封膜、吸管、标签比例和“只手大小”的参照；场景里的既有包装会被模型当成主体。
- 修法：写死 “normal 500ml sealed takeaway cup, flat dome lid, straw, small blank paper label about one third of cup height, roughly hand size”；negative 加 `oversized cup, soda cup, fast food cup, bottle, can, jar, yogurt cup, brand logos`。冰箱/货架镜头明确“只放同款杯”，生成后目检瓶罐与品牌，发现即重渲染。

## F11 角色标记与伤势漂移

- 现象：头盔白兔贴纸时有时无、持头盔的左右手互换、两颊多出伤、雨衣 037 丢失。
- 机制：每镜独立起关键帧；提示词只锁脸，没锁标志物、持物手和伤势数量，Qwen 会把参考图的疤痕扩散到两颊。
- 修法：先修参考图——参考图本身多疤或重复 037 时，所有派生画面都会漂移，必须先做单疤、单 037 的干净参考。贴纸位置写死为“只贴后壳”：正面镜头写 `front of the helmet completely blank, no sticker`，背面/3-4 背视角写 `back shell facing camera, white rabbit sticker on the back shell`；正面 prompt 绝不能出现“贴纸可见”。再锁 `left hand holding helmet / right hand empty`、`exactly one old healed scar on the right eyebrow to right cheekbone, both cheeks otherwise clear, no other injuries, no blood`、`037 clearly printed and clean on the back only`；H3 prompt 再写一遍。关键帧验收先看贴纸位置、持物手、单疤、037 四项，再看构图。近景擦除贴纸会改构图或加对侧疤，失败时改用自然单疤版本，不要人造疤。

## F12 真实品牌泄漏

- 现象：AI 在冰箱、货架、外卖包装上生成可乐/芬达/酸奶等真实品牌。
- 机制：模型先验倾向于可识别包装；只写 “no brand logos” 往往不够。
- 修法：生成前 negative 写明 `soda bottles, water bottles, beer bottles, jars, cans, yogurt cups, printed label text`，并指定“每杯都是同款空白标签”；生成后目检，出现品牌即重渲染。不要用后期打码掩盖，打码会破坏真实感并留下明显补丁。

## F13 生成模型烘焙 UI/文字

- 现象：直播界面、状态栏、弹幕条被直接画进关键帧或视频，中文字形错乱（如 “Onlte 115181”），后期无法直接使用。
- 机制：提示词描述了“透过直播屏幕看”等场景，模型把“直播 UI”当成画面内容；文字是生成模型的弱项。
- 修法：关键帧 prompt 明确 `No text, numbers or interface is drawn in the frame; the UI is added in editing`，negative 加 `text, numbers, interface, status bar, speech bubble, icons`。已烘入的 UI 用图像编辑去掉，再单独画透明 PNG 层（`{shot_id}_uionly.png`），剪辑时 ffmpeg `overlay` 合成；这样中文锐利、可改文案，也不随视频抖动变形。

## F14 等待器超时但任务仍在跑

- 现象：批处理报 `TimeoutError: ... not finished in 1800s`，但 ComfyUI 队列继续执行，稍后产物出现在 `output/`。
- 机制：等待器从“提交”开始计时，包含前面排队的时间；长任务或队列靠前插队时会先超时。ComfyUI 新提交可跳到已有 pending 之前，编辑任务会被 H3 大任务压住。
- 修法：超时只说明等待结束，不代表任务失败。先用 `/queue` 和 `/history/{prompt_id}` 核实，再检查 `output/{project}/` 是否已有新文件；有则手动拷贝并抽帧验收。重渲与轻量编辑分开排队：先清空编辑队列，再提交 H3，避免 H3 插队把编辑挤后。

## F15 TTS 清单文本过期

- 现象：字幕已改成新台词，成片里却听见旧音（本轮 s021 实际播放“第37杯，该你喝了。”）。
- 机制：TTS 清单按 id 缓存文本与秒数；改字幕时只改了时间线，没有重跑该行 TTS，manifest 仍保留旧文本。
- 修法：改任何台词后，逐行比对 `tts_manifest.json` 的 `text` 与时间线字幕，不一致的行必须用 `--only <id>` 重配；混音前用 ASR 抽验成片对白段，发现同音之外的整句不符即回查清单。

## F16 CPU TTS 内存不足段错误

- 现象：`generate_tts.py` 在 `loading IndexTTS2` 后直接 Segmentation fault（exit 139），无 Python 异常。
- 机制：ComfyUI 空闲时仍缓存模型，系统可用内存可能只剩 5–6GB；IndexTTS2 加载峰值超过剩余内存。
- 修法：先 `POST /free {"unload_models":true,"free_memory":true}` 释放 ComfyUI 缓存，确认可用内存 >20GB 再跑；同一失败不要连续盲重试。

## F17 剪辑脚本相对路径导致 concat 双拼

- 现象：ffmpeg 报找不到 `06_edit/ep01_cut_v3/06_edit/ep01_cut_v3/clip_...mp4`。
- 机制：`build_cut.py --work` 接受相对路径，写进 concat.txt 的条目相对 concat.txt 所在目录，被解析成重复层级。
- 修法：`--work` 一律传绝对路径（`D:/...`）；`--output` 仍可是导出目录内的文件名。

## F18 字幕安全区与播报重叠

- 现象：竖屏底部字幕被抖音 UI 遮挡；长系统播报压到下一句台词（本轮 s022 4.95s 压到 s023 0.68s）。
- 机制：ASS `MarginV` 过小；TTS 按原句字数生成，atempo 上限 1.30 后仍超出字幕窗。
- 修法：竖屏 `MarginV` 用到 250（768×1344 基准）；系统播报优先改写短句（“第38单，送到您家门口。”2.77s），不要靠极限变速硬塞；混音前核对 `语音起点 + 适配后时长 ≤ 下一句起点`。

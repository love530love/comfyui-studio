#!/usr/bin/env python3
"""Validate short-drama shotlist continuity and build review contact sheets."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

TRANSITIONS = {"open", "chain", "cut", "match_cut", "insert", "state_change", "time_jump"}
STATE_CHANGING = {"state_change", "time_jump"}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def contains(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


NEGATION = re.compile(r"\b(?:no|without|never|not)\s+(?:(?:a|an|the|any)\s+)?$")


def contains_positive(haystack: str, needle: str) -> bool:
    """正向包含：'no visor' 不算出现禁用词 'visor'。"""
    text = norm(haystack)
    term = norm(needle)
    start = 0
    while True:
        index = text.find(term, start)
        if index == -1:
            return False
        if not NEGATION.search(text[max(0, index - 16):index]):
            return True
        start = index + len(term)


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class Checker:
    def __init__(self, project: Path, shotlist_path: Path, contracts_path: Path, strict: bool, check_files: bool) -> None:
        self.project = project
        self.shotlist_path = shotlist_path
        self.contracts_path = contracts_path
        self.strict = strict
        self.check_files = check_files
        self.report = Report()
        self.contracts = self._load_yaml(contracts_path)
        self.shotlist = self._load_yaml(shotlist_path)
        self.characters = self.contracts.get("characters", {}) if isinstance(self.contracts, dict) else {}
        self.props = self.contracts.get("props", {}) if isinstance(self.contracts, dict) else {}
        self.episode = self.shotlist.get("episode", "?") if isinstance(self.shotlist, dict) else "?"
        self.seen_ids: set[str] = set()

    def _load_yaml(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} 不是 YAML 映射")
        return data

    def where(self, shot_id: str, scene: int | None = None) -> str:
        if scene is None:
            return f"ep{self.episode}/{shot_id}"
        return f"ep{self.episode}/scene{scene}/{shot_id}"

    def run(self) -> Report:
        self.check_top()
        scenes = self.shotlist.get("scenes") or []
        if not scenes:
            self.report.error(f"ep{self.episode}", "没有 scenes")
        for scene in scenes:
            self.check_scene(scene)
        return self.report

    def check_top(self) -> None:
        target = self.shotlist.get("duration_target")
        if target is None:
            self.report.error(f"ep{self.episode}", "缺少 duration_target")
            return
        total = 0.0
        video_count = 0
        for scene in self.shotlist.get("scenes") or []:
            for shot in scene.get("shots") or []:
                total += float(shot.get("duration") or 0)
                if shot.get("video"):
                    video_count += 1
        if abs(total - float(target)) > 1e-6:
            self.report.error(f"ep{self.episode}", f"时长不闭合: sum={total:.3f}s target={float(target):.3f}s")
        video_target = self.shotlist.get("video_target")
        if isinstance(video_target, dict):
            video_min = int(video_target.get("min", 3))
            video_max = int(video_target.get("max", 5))
        elif isinstance(video_target, list) and len(video_target) == 2:
            video_min, video_max = int(video_target[0]), int(video_target[1])
        else:
            video_min, video_max = 3, 5
        if video_count < video_min or video_count > video_max:
            self.report.warn(f"ep{self.episode}", f"视频镜 {video_count} 个，目标 {video_min}–{video_max} 个")

    def check_scene(self, scene: dict) -> None:
        scene_no = scene.get("scene")
        shots = scene.get("shots") or []
        if scene.get("axis") is None and len(shots) > 1:
            self.report.warn(f"ep{self.episode}/scene{scene_no}", "多镜场景没有写 axis（轴线/机位侧）")
        defaults = scene.get("state_defaults") or {}
        self.validate_state_map(defaults, f"ep{self.episode}/scene{scene_no}/state_defaults")

        prev_shot = None
        prev_state = None
        prev_axis = None
        for index, shot in enumerate(shots):
            shot_id = shot.get("id") or f"<idx{index}>"
            self.check_shot(scene_no, shot)
            state = self.effective_state(defaults, shot)
            axis = shot.get("axis_side")
            transition = shot.get("transition") or {}
            ttype = transition.get("type")

            if prev_shot is not None:
                self.check_transition(prev_shot, shot, state, prev_state, axis, prev_axis, transition)
            elif ttype and ttype != "open":
                self.report.warn(self.where(shot_id, scene_no), f"场首镜头 transition.type={ttype}，应为 open")

            prev_shot, prev_state, prev_axis = shot, state, axis

    def check_shot(self, scene_no, shot: dict) -> None:
        shot_id = shot.get("id") or "<missing>"
        where = self.where(shot_id, scene_no)
        required = ["id", "duration", "shot_type", "camera", "beat", "characters", "prompt", "seed", "keyframe", "video", "status"]
        for field in required:
            if shot.get(field) in (None, ""):
                self.report.error(where, f"缺少字段 {field}")
        if shot_id in self.seen_ids:
            self.report.error(where, f"id 重复: {shot_id}")
        self.seen_ids.add(shot_id)

        duration = float(shot.get("duration") or 0)
        if duration <= 0:
            self.report.error(where, "duration 必须大于 0")
        dialogue = shot.get("dialogue") or ""
        if dialogue and duration < len(dialogue) / 4.5 + 0.2 - 1e-6:
            self.report.error(where, f"台词 {len(dialogue)} 字需要 ≥{len(dialogue) / 4.5 + 0.2:.2f}s，当前 {duration:.2f}s")

        self.validate_state_map(shot.get("state") or {}, where)
        prompt = shot.get("prompt") or ""
        negative = shot.get("negative") or ""
        strict_prompt = self.strict or bool(shot.get("prompt_lock"))

        for char in as_list(shot.get("characters")):
            contract = self.characters.get(char)
            if contract is None:
                self.report.error(where, f"角色 {char} 不在 contracts.yaml")
                continue
            anchor = contract.get("anchor") or ""
            if anchor and not contains(prompt, anchor):
                message = f"prompt 未逐字包含 {char} 锚点"
                if strict_prompt:
                    self.report.error(where, message)
                else:
                    self.report.warn(where, message)
            for term in as_list(contract.get("negative_required")):
                if not contains(negative, term):
                    message = f"negative 缺少必填词 {term!r}"
                    if strict_prompt:
                        self.report.error(where, message)
                    else:
                        self.report.warn(where, message)
            for term in as_list(contract.get("forbidden_positive")):
                if contains_positive(prompt, term):
                    self.report.error(where, f"prompt 出现禁用词 {term!r}")
            self.check_required_phrases(where, char, contract, shot, prompt, negative)

        for prop_name, value in (shot.get("props") or {}).items():
            contract = self.props.get(prop_name)
            if contract is None:
                self.report.warn(where, f"道具 {prop_name} 不在 contracts.yaml")
                continue
            if str(value).lower() == "present":
                anchor = contract.get("anchor") or ""
                if anchor and not contains(prompt, anchor):
                    message = f"prompt 未包含道具 {prop_name} 锚点"
                    if strict_prompt:
                        self.report.error(where, message)
                    else:
                        self.report.warn(where, message)
            for term in as_list(contract.get("forbidden")):
                if contains_positive(prompt, term):
                    self.report.error(where, f"prompt 出现道具禁用词 {term!r}")

        refs = as_list(shot.get("refs"))
        if strict_prompt and not refs:
            self.report.warn(where, "没有 refs 参考图")
        if self.check_files:
            for ref in refs:
                self.check_file(ref, where, "ref")
            self.check_file(shot.get("keyframe"), where, "keyframe")
            if shot.get("last_frame"):
                self.check_file(shot.get("last_frame"), where, "last_frame")

        if strict_prompt and not as_list(shot.get("acceptance")):
            self.report.warn(where, "没有 acceptance 目检项")

    def check_required_phrases(self, where, char, contract, shot, prompt, negative) -> None:
        state = self.effective_state({}, shot).get(char, {})
        shot_type = shot.get("shot_type")
        combined = f"{prompt}\n{negative}"
        for rule in contract.get("required_phrases") or []:
            when = rule.get("when") or {}
            if not self.condition_matches(when, state, shot_type):
                continue
            for phrase in as_list(rule.get("phrases")):
                if not contains(combined, phrase):
                    message = f"{char} 条件短语缺失 {phrase!r}（when={when}）"
                    if self.strict or shot.get("prompt_lock"):
                        self.report.error(where, message)
                    else:
                        self.report.warn(where, message)

    @staticmethod
    def condition_matches(when: dict, state: dict, shot_type) -> bool:
        for key, expected in when.items():
            if key == "shot_type":
                if shot_type not in as_list(expected):
                    return False
            elif state.get(key) != expected:
                return False
        return True

    def validate_state_map(self, state_map: dict, where: str) -> None:
        if not isinstance(state_map, dict):
            self.report.error(where, "state 必须是按角色分组的映射")
            return
        for char, values in state_map.items():
            contract = self.characters.get(char)
            if contract is None:
                self.report.error(where, f"状态中的角色 {char} 不在 contracts.yaml")
                continue
            if not isinstance(values, dict):
                self.report.error(where, f"{char} 的状态必须是映射")
                continue
            allowed = contract.get("states") or {}
            for var, value in values.items():
                if var not in allowed:
                    self.report.warn(where, f"{char}.{var} 没有在 contracts.yaml 声明")
                    continue
                if value not in as_list(allowed[var]):
                    self.report.error(where, f"{char}.{var}={value!r} 非法，允许: {allowed[var]}")

    @staticmethod
    def effective_state(defaults: dict, shot: dict) -> dict:
        merged: dict[str, dict] = {}
        for source in (defaults, shot.get("state") or {}):
            for char, values in (source or {}).items():
                merged.setdefault(char, {}).update(values or {})
        return merged

    def check_transition(self, prev_shot, shot, state, prev_state, axis, prev_axis, transition) -> None:
        shot_id = shot.get("id") or "<missing>"
        where = self.where(shot_id)
        ttype = transition.get("type")
        if not ttype:
            if self.strict:
                self.report.error(where, "缺少 transition.type")
            if state != prev_state:
                self.report.warn(where, "状态变化但没有 transition 说明")
            return
        if ttype not in TRANSITIONS:
            self.report.error(where, f"未知 transition.type={ttype!r}")
            return

        state_changed = state != prev_state
        if state_changed and ttype not in STATE_CHANGING:
            self.report.error(where, f"transition={ttype} 不允许状态变化（改用 state_change/time_jump）")
        if ttype == "state_change" and not state_changed:
            self.report.error(where, "state_change 但状态没有变化")
        if ttype in STATE_CHANGING and not transition.get("motivated_by"):
            self.report.error(where, f"{ttype} 缺少 motivated_by")

        chain_from = transition.get("chain_from") or shot.get("chain_from")
        if ttype == "chain":
            if not chain_from:
                self.report.error(where, "chain 缺少 chain_from")
            elif chain_from != prev_shot.get("id"):
                self.report.error(where, f"chain_from={chain_from} 不是同场上一镜 {prev_shot.get('id')}")
            if state_changed:
                self.report.error(where, "chain 必须保持状态完全一致")
            if axis and prev_axis and axis != prev_axis:
                self.report.error(where, f"chain 必须同侧，{prev_axis}→{axis}")
        elif chain_from and chain_from != prev_shot.get("id"):
            self.report.error(where, f"chain_from={chain_from} 不是同场上一镜 {prev_shot.get('id')}")

        if axis and prev_axis and axis != prev_axis and ttype != "time_jump" and not transition.get("motivated_by"):
            self.report.error(where, f"同场越轴 {prev_axis}→{axis}，需中性镜或 motivated_by")

    def check_file(self, rel: str | None, where: str, label: str) -> None:
        if not rel:
            return
        path = (self.project / rel).resolve()
        if not path.exists():
            self.report.error(where, f"{label} 文件不存在: {rel}")


def load_font(size: int):
    from PIL import ImageFont
    for name in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_sheet(items: list[tuple[Path, str]], out_path: Path, title: str, columns: int = 4) -> None:
    from PIL import Image, ImageDraw
    if not items:
        print(f"[sheet] 跳过 {out_path}: 没有可用图片")
        return
    thumb_w, thumb_h = 320, 480
    label_h = 34
    rows = (len(items) + columns - 1) // columns
    title_h = 44
    sheet = Image.new("RGB", (columns * thumb_w, title_h + rows * (thumb_h + label_h)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    font = load_font(18)
    small = load_font(14)
    draw.text((12, 12), title, fill=(235, 235, 235), font=font)
    for index, (path, label) in enumerate(items):
        row, col = divmod(index, columns)
        x = col * thumb_w
        y = title_h + row * (thumb_h + label_h)
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w, thumb_h))
                px = x + (thumb_w - image.width) // 2
                py = y + (thumb_h - image.height) // 2
                sheet.paste(image, (px, py))
        except Exception as exc:  # noqa: BLE001 - 单张坏图不应中断整张接触表
            draw.text((x + 8, y + 8), f"load failed: {path.name}", fill=(255, 120, 120), font=small)
            print(f"[sheet] 跳过坏图 {path}: {exc}")
        draw.text((x + 6, y + thumb_h + 4), label, fill=(220, 220, 220), font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"[sheet] {out_path} ({len(items)} 张)")


def build_keyframe_sheet(project: Path, shotlist: dict, out_path: Path) -> None:
    items = []
    for scene in shotlist.get("scenes") or []:
        for shot in scene.get("shots") or []:
            rel = shot.get("keyframe")
            if not rel:
                continue
            path = (project / rel).resolve()
            if path.exists():
                state = shot.get("state") or {}
                bits = []
                for char, values in state.items():
                    bits.append(char + ":" + ",".join(f"{k}={v}" for k, v in values.items()))
                label = f"{shot.get('id')} {shot.get('duration')}s {shot.get('shot_type')} " + " ".join(bits)
                items.append((path, label))
    make_sheet(items, out_path, f"EP{shotlist.get('episode')} keyframes - G3 continuity")


def find_video(project: Path, episode: int, shot_id: str, video_dir: Path | None) -> Path | None:
    root = video_dir or (project / "04_video" / f"ep{int(episode):02d}")
    if not root.exists():
        return None
    candidates = sorted(root.glob(f"{shot_id}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def extract_frame(video: Path, time_arg: list[str], out_path: Path) -> bool:
    command = ["ffmpeg", "-y", "-loglevel", "error", *time_arg, "-i", str(video), "-frames:v", "1", str(out_path)]
    try:
        subprocess.run(command, check=True, timeout=60)
        return out_path.exists()
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"[video-sheet] 抽帧失败 {video.name}: {exc}")
        return False


def build_video_sheet(project: Path, shotlist: dict, out_path: Path, video_dir: Path | None) -> None:
    items = []
    with tempfile.TemporaryDirectory(prefix="ep_contact_") as tmp:
        tmp_dir = Path(tmp)
        for scene in shotlist.get("scenes") or []:
            for shot in scene.get("shots") or []:
                if not shot.get("video"):
                    continue
                shot_id = shot.get("id") or "shot"
                video = find_video(project, shotlist.get("episode", 0), shot_id, video_dir)
                if video is None:
                    print(f"[video-sheet] 缺视频: {shot_id}")
                    continue
                first = tmp_dir / f"{shot_id}_first.jpg"
                last = tmp_dir / f"{shot_id}_last.jpg"
                if extract_frame(video, ["-ss", "0"], first):
                    items.append((first, f"{shot_id} first"))
                if extract_frame(video, ["-sseof", "-0.08"], last):
                    items.append((last, f"{shot_id} last"))
    make_sheet(items, out_path, f"EP{shotlist.get('episode')} video boundaries - G4 continuity")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="检查短剧分镜连续性并生成接触表")
    parser.add_argument("--project", required=True, help="项目根目录（含 shotlist/ 与 01_series/continuity/）")
    parser.add_argument("--episode", required=True, type=int, help="集数，用于定位 shotlist/epNN.yaml")
    parser.add_argument("--shotlist", help="显式指定分镜文件，默认 <project>/shotlist/epNN.yaml")
    parser.add_argument("--contracts", help="显式指定契约文件，默认 <project>/01_series/continuity/contracts.yaml")
    parser.add_argument("--strict", action="store_true", help="ep02 起使用：缺失 transition/锚点/负面词升级为 error")
    parser.add_argument("--check-files", action="store_true", help="检查 keyframe/last_frame/refs 文件是否存在")
    parser.add_argument("--sheet", help="输出关键帧接触表 PNG")
    parser.add_argument("--video-sheet", help="输出视频首尾帧边界表 PNG")
    parser.add_argument("--video-dir", help="视频目录，默认 <project>/04_video/epNN")
    parser.add_argument("--json", help="把报告写入 JSON")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    shotlist_path = Path(args.shotlist).expanduser().resolve() if args.shotlist else project / "shotlist" / f"ep{args.episode:02d}.yaml"
    contracts_path = Path(args.contracts).expanduser().resolve() if args.contracts else project / "01_series" / "continuity" / "contracts.yaml"

    try:
        checker = Checker(project, shotlist_path, contracts_path, args.strict, args.check_files)
        report = checker.run()
    except (FileNotFoundError, ValueError) as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 2

    shotlist = checker.shotlist
    print(f"EP{shotlist.get('episode')} 连续性检查：{len(report.errors)} error / {len(report.warnings)} warning")
    for line in report.errors:
        print(f"  ERROR   {line}")
    for line in report.warnings:
        print(f"  WARNING {line}")

    if args.json:
        payload = {
            "episode": shotlist.get("episode"),
            "shotlist": str(shotlist_path),
            "contracts": str(contracts_path),
            "errors": report.errors,
            "warnings": report.warnings,
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[json] {args.json}")

    if args.sheet:
        build_keyframe_sheet(project, shotlist, Path(args.sheet).expanduser().resolve())
    if args.video_sheet:
        build_video_sheet(project, shotlist, Path(args.video_sheet).expanduser().resolve(), Path(args.video_dir).expanduser().resolve() if args.video_dir else None)

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())

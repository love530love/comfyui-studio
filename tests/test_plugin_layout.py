import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
MACHINE_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
SECRET = re.compile(r"(sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{20,}|X-API-Key)")


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        raise AssertionError("frontmatter must start on the first line")
    end = text.find("\n---", 4)
    if end == -1:
        raise AssertionError("frontmatter is not closed")
    body = text[4:end]
    data = {}
    for line in body.splitlines():
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip('"')
    return data


class ManifestTests(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((ROOT / ".qoder-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "comfyui-studio")
        self.assertEqual(manifest["name"], ROOT.name)
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(manifest["description"])
        self.assertEqual(manifest["author"]["name"], "love530love")

    def test_mcp_config(self):
        cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        servers = cfg["mcpServers"]
        self.assertEqual(set(servers), {"comfyui-studio-runner", "comfyui-studio-pycharm"})
        for name, server in servers.items():
            self.assertEqual(server["command"], "python", name)
            args = server["args"]
            self.assertEqual(len(args), 1)
            self.assertTrue(args[0].startswith("${QODER_PLUGIN_ROOT}/bin/"), name)
            target = ROOT / args[0].replace("${QODER_PLUGIN_ROOT}/", "")
            self.assertTrue(target.is_file(), f"{name} launcher missing: {target}")


class SkillTests(unittest.TestCase):
    def skill_dirs(self):
        return sorted(p for p in SKILLS.iterdir() if p.is_dir())

    def test_skills_exist(self):
        names = {p.name for p in self.skill_dirs()}
        self.assertEqual(names, {"comfyui-image", "comfyui-video", "short-drama-pipeline"})

    def test_frontmatter(self):
        for skill in self.skill_dirs():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            meta = parse_frontmatter(text)
            self.assertEqual(meta.get("name"), skill.name, skill.name)
            self.assertGreater(len(meta.get("description", "")), 20, skill.name)

    def test_reference_links(self):
        for skill in self.skill_dirs():
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            for link in re.findall(r"`(references/[^`]+\.md)`", text):
                self.assertTrue((skill / link).is_file(), f"{skill.name}: missing {link}")

    def test_no_machine_paths_or_secrets(self):
        targets = list(SKILLS.rglob("*.md")) + list((ROOT / "bin").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))
        for path in targets:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(MACHINE_PATH.search(text), f"machine path in {path}")
            self.assertIsNone(SECRET.search(text), f"possible secret in {path}")


class LauncherTests(unittest.TestCase):
    def test_launchers_compile(self):
        for path in (ROOT / "bin").glob("*.py"):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_setup_compiles(self):
        path = ROOT / "scripts" / "setup.py"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()

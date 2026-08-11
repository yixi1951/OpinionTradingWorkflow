"""Prompt version registry for sentiment / event / risk scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class PromptVersion:
    name: str
    version: str
    scenario: str
    template: str
    few_shot: List[Dict[str, Any]]
    active: bool = True


DEFAULT_PROMPTS: Dict[str, PromptVersion] = {
    "sentiment@v1": PromptVersion(
        name="sentiment",
        version="v1",
        scenario="sentiment",
        template=(
            "你是 A 股中文舆情情绪评分引擎。\n"
            "必须只输出严格 JSON：{{\"scores\":[n1,n2,...]}}。\n"
            "分数范围 [-1,1]，越大越正面。不确定用 0.0。\n"
            "输入：\n{texts}"
        ),
        few_shot=[
            {"input": ["茅台放量突破"], "scores": [0.72]},
            {"input": ["利空落地担心阴跌"], "scores": [-0.65]},
        ],
        active=True,
    ),
    "event@v1": PromptVersion(
        name="event",
        version="v1",
        scenario="event",
        template=(
            "从文本中抽取事件类型，只输出 JSON："
            "{{\"events\":[{{\"type\":\"earnings|policy|mna|risk|rumor|technical|general\",\"confidence\":0.0}}]}}。\n"
            "输入：\n{texts}"
        ),
        few_shot=[],
        active=True,
    ),
    "risk@v1": PromptVersion(
        name="risk",
        version="v1",
        scenario="risk",
        template=(
            "识别文本风险信号，只输出 JSON："
            "{{\"risks\":[{{\"level\":\"high|medium|low\",\"score\":0.0}}]}}。\n"
            "输入：\n{texts}"
        ),
        few_shot=[],
        active=True,
    ),
}


class PromptRegistry:
    def __init__(self, root: str = "config/prompts") -> None:
        self.root = Path(root)
        self._items: Dict[str, PromptVersion] = dict(DEFAULT_PROMPTS)
        self._active: Dict[str, str] = {
            "sentiment": "v1",
            "event": "v1",
            "risk": "v1",
        }
        self.reload()

    def reload(self) -> None:
        if not self.root.exists() or yaml is None:
            return
        registry_file = self.root / "registry.yaml"
        if registry_file.exists():
            data = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
            for scenario, ver in (data.get("active") or {}).items():
                self._active[str(scenario)] = str(ver)
        for path in self.root.glob("*.yaml"):
            if path.name == "registry.yaml":
                continue
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            key = f"{raw.get('name')}@{raw.get('version')}"
            self._items[key] = PromptVersion(
                name=str(raw.get("name")),
                version=str(raw.get("version")),
                scenario=str(raw.get("scenario", raw.get("name"))),
                template=str(raw.get("template", "")),
                few_shot=list(raw.get("few_shot") or []),
                active=bool(raw.get("active", True)),
            )

    def get(self, scenario: str, version: Optional[str] = None) -> PromptVersion:
        ver = version or self._active.get(scenario, "v1")
        key = f"{scenario}@{ver}"
        if key not in self._items:
            # fallback to default sentiment
            return self._items["sentiment@v1"]
        return self._items[key]

    def set_active(self, scenario: str, version: str) -> None:
        key = f"{scenario}@{version}"
        if key not in self._items:
            raise KeyError(f"unknown prompt {key}")
        self._active[scenario] = version
        if self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            payload = {"active": self._active}
            if yaml is not None:
                (self.root / "registry.yaml").write_text(
                    yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
                )

    def list_versions(self, scenario: Optional[str] = None) -> List[Dict[str, Any]]:
        out = []
        for key, p in sorted(self._items.items()):
            if scenario and p.scenario != scenario:
                continue
            out.append(
                {
                    "key": key,
                    "scenario": p.scenario,
                    "version": p.version,
                    "active": self._active.get(p.scenario) == p.version,
                }
            )
        return out

    def render(self, scenario: str, texts: List[str], version: Optional[str] = None) -> str:
        prompt = self.get(scenario, version)
        numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
        body = prompt.template.format(texts=numbered)
        if prompt.few_shot:
            examples = ["Few-shot:"]
            for ex in prompt.few_shot[:4]:
                examples.append(f"- input={ex.get('input')} -> scores={ex.get('scores')}")
            body = "\n".join(examples) + "\n\n" + body
        return body

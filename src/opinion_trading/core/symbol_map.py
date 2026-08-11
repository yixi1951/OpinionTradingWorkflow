"""Stock name ↔ code mapping library for entity linking.

Handles aliases, short names, and concept-confusion (e.g. 茅台 → 600519.SH).
Seed map covers a liquid HS300 subset; can be extended via CSV / akshare.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_CODE_RE = re.compile(r"(?<!\d)([0-6]\d{5})(?!\d)")

# Liquid HS300 / blue-chip seed (name + aliases). Enough for student-scale coverage.
SEED_ALIAS_MAP: Dict[str, List[str]] = {
    "600519.SH": ["贵州茅台", "茅台", "茅台酒", "600519"],
    "000858.SZ": ["五粮液", "宜宾五粮液", "000858"],
    "600036.SH": ["招商银行", "招行", "600036"],
    "601318.SH": ["中国平安", "平安", "平安保险", "601318"],
    "000001.SZ": ["平安银行", "深发展", "000001"],
    "601166.SH": ["兴业银行", "兴业", "601166"],
    "600000.SH": ["浦发银行", "浦发", "600000"],
    "601398.SH": ["工商银行", "工行", "601398"],
    "601939.SH": ["建设银行", "建行", "601939"],
    "601288.SH": ["农业银行", "农行", "601288"],
    "600276.SH": ["恒瑞医药", "恒瑞", "600276"],
    "000333.SZ": ["美的集团", "美的", "000333"],
    "000651.SZ": ["格力电器", "格力", "000651"],
    "002415.SZ": ["海康威视", "海康", "002415"],
    "300750.SZ": ["宁德时代", "宁德", "时代新能源", "300750"],
    "601012.SH": ["隆基绿能", "隆基", "隆基股份", "601012"],
    "600900.SH": ["长江电力", "长电", "600900"],
    "601888.SH": ["中国中免", "中免", "免税", "601888"],
    "600030.SH": ["中信证券", "中信", "600030"],
    "601688.SH": ["华泰证券", "华泰", "601688"],
    "000568.SZ": ["泸州老窖", "老窖", "000568"],
    "002304.SZ": ["洋河股份", "洋河", "002304"],
    "600887.SH": ["伊利股份", "伊利", "600887"],
    "000002.SZ": ["万科A", "万科", "000002"],
    "600048.SH": ["保利发展", "保利", "600048"],
    "601668.SH": ["中国建筑", "中建", "601668"],
    "600028.SH": ["中国石化", "石化", "600028"],
    "601857.SH": ["中国石油", "中石油", "601857"],
    "601088.SH": ["中国神华", "神华", "601088"],
    "600809.SH": ["山西汾酒", "汾酒", "600809"],
}

# Ambiguous short names that should NOT map alone (concept confusion)
AMBIGUOUS_ALIASES = {"平安", "中信", "银行", "白酒", "新能源", "军工", "芯片"}


class SymbolMapper:
    """Bidirectional name/code resolver with ambiguity guards."""

    def __init__(self, alias_map: Optional[Mapping[str, Sequence[str]]] = None) -> None:
        self.alias_to_symbol: Dict[str, str] = {}
        self.symbol_to_aliases: Dict[str, List[str]] = {}
        self._load(alias_map or SEED_ALIAS_MAP)

    def _load(self, alias_map: Mapping[str, Sequence[str]]) -> None:
        for symbol, aliases in alias_map.items():
            sym = str(symbol).strip().upper()
            vals = [str(a).strip() for a in aliases if str(a).strip()]
            self.symbol_to_aliases[sym] = vals
            for alias in vals:
                key = alias.lower() if alias.isascii() else alias
                # Prefer longer / more specific aliases; skip ambiguous alone
                if alias in AMBIGUOUS_ALIASES and len(vals) > 1:
                    # still register but mark via longer context matching later
                    pass
                self.alias_to_symbol[key] = sym
            code = sym.split(".", 1)[0]
            self.alias_to_symbol[code] = sym

    @classmethod
    def from_json(cls, path: str | Path) -> "SymbolMapper":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data)

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.symbol_to_aliases, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def extend(self, alias_map: Mapping[str, Sequence[str]]) -> None:
        self._load(alias_map)

    def resolve(self, text: str) -> List[Tuple[str, str]]:
        """Return list of (symbol, matched_token) found in text."""
        blob = str(text or "")
        hits: List[Tuple[str, str]] = []
        seen = set()

        for m in _CODE_RE.finditer(blob):
            code = m.group(1)
            sym = self.alias_to_symbol.get(code)
            if sym and sym not in seen:
                seen.add(sym)
                hits.append((sym, code))

        # Longer aliases first to reduce false positives
        aliases_sorted = sorted(self.alias_to_symbol.keys(), key=len, reverse=True)
        for alias in aliases_sorted:
            if alias.isdigit():
                continue
            if alias in AMBIGUOUS_ALIASES:
                continue
            needle = alias
            if needle.isascii():
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", blob, re.I):
                    sym = self.alias_to_symbol[alias]
                    if sym not in seen:
                        seen.add(sym)
                        hits.append((sym, alias))
            elif needle in blob:
                sym = self.alias_to_symbol[alias]
                if sym not in seen:
                    seen.add(sym)
                    hits.append((sym, alias))
        return hits

    def match_symbol(self, text: str, target_symbol: str) -> Tuple[bool, List[str]]:
        target = str(target_symbol).strip().upper()
        hits = self.resolve(text)
        tokens = [tok for sym, tok in hits if sym == target]
        if tokens:
            return True, tokens
        # Soft match: crawler already scoped to symbol page with empty/short text
        soft = bool(target) and len(str(text or "").strip()) < 12
        return soft, tokens

    def aliases_for(self, symbol: str) -> List[str]:
        return list(self.symbol_to_aliases.get(str(symbol).strip().upper(), []))


_GLOBAL_MAPPER: Optional[SymbolMapper] = None


def get_symbol_mapper(map_path: Optional[str] = None) -> SymbolMapper:
    global _GLOBAL_MAPPER
    if map_path:
        return SymbolMapper.from_json(map_path)
    if _GLOBAL_MAPPER is None:
        default = Path("config/symbol_alias_map.json")
        if default.exists():
            _GLOBAL_MAPPER = SymbolMapper.from_json(default)
        else:
            _GLOBAL_MAPPER = SymbolMapper()
    return _GLOBAL_MAPPER


def build_alias_map_from_rows(rows: Iterable[Mapping[str, str]]) -> Dict[str, List[str]]:
    """Build alias map from rows with keys symbol, name, aliases(optional csv)."""
    out: Dict[str, List[str]] = {}
    for row in rows:
        sym = str(row.get("symbol", "")).strip().upper()
        if not sym:
            continue
        names = [str(row.get("name", "")).strip()]
        extra = str(row.get("aliases", "")).strip()
        if extra:
            names.extend([x.strip() for x in extra.split(",") if x.strip()])
        code = sym.split(".", 1)[0]
        names.append(code)
        cleaned = [n for n in names if n]
        out[sym] = list(dict.fromkeys(cleaned))
    return out

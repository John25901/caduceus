from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.search_engine import HybridTariffEngine
from backend.app.ingestion.tabular_parser import TabularEquipmentParser

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures"


def evaluate(path: Path, engine: HybridTariffEngine) -> dict:
    parsed = TabularEquipmentParser().parse_path(path)
    eligible = [i for i in parsed.items if i.code_sh_source]
    top1 = top3 = 0
    details = []
    for item in eligible:
        query = item.designation_source + (f". {item.specifications}" if item.specifications else "")
        candidates = engine.search(query, top_k=5)
        codes = [c.code_sh for c in candidates]
        expected = item.code_sh_source
        top1 += bool(codes and codes[0] == expected)
        top3 += expected in codes[:3]
        details.append((item.designation_source, expected, codes[:3]))
    n = len(eligible)
    return {
        "file": path.name,
        "n": n,
        "top1_accuracy": top1 / n if n else 0,
        "top3_recall": top3 / n if n else 0,
        "details": details,
    }


def main():
    settings = Settings(enable_semantic=False)
    repo = CamcisRepository(ROOT / "data" / "reference" / "Code_SH_CAMCIS.xlsx")
    engine = HybridTariffEngine(repo, settings, use_history=False)
    for filename in ["NETIC_reference.xlsx", "FRANCY_GARDEN_reference.xlsx"]:
        r = evaluate(FIX / filename, engine)
        print(f"{r['file']}: n={r['n']} top1={r['top1_accuracy']:.1%} top3={r['top3_recall']:.1%}")
        misses = [d for d in r["details"] if d[1] not in d[2]]
        print(f"  misses top3: {len(misses)}")
        for d in misses[:10]:
            print("   -", d)


if __name__ == "__main__":
    main()

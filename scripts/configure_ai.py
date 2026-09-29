from __future__ import annotations

import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"


def load_lines() -> list[str]:
    if ENV.exists():
        return ENV.read_text(encoding="utf-8").splitlines()
    example = ROOT / ".env.example"
    return example.read_text(encoding="utf-8").splitlines() if example.exists() else []


def upsert(lines: list[str], key: str, value: str) -> list[str]:
    prefix = key + "="
    out = []
    replaced = False
    for line in lines:
        if line.startswith(prefix):
            out.append(prefix + value)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(prefix + value)
    return out


def main() -> int:
    print("CADUCEUS — configuration de l'assistance IA")
    print("Les clés sont conservées uniquement dans .env sur cette machine et ne sont jamais exportées dans les rapports.")
    print("1) NVIDIA / Kimi (PoC)\n2) OpenAI\n3) Les deux\n0) Annuler")
    choice = input("Choix : ").strip()
    if choice == "0" or choice not in {"1", "2", "3"}:
        print("Aucune modification.")
        return 0
    lines = load_lines()
    if choice in {"1", "3"}:
        key = getpass.getpass("NVIDIA_API_KEY (saisie masquée) : ").strip()
        model = input("Modèle NVIDIA [moonshotai/kimi-k3] : ").strip() or "moonshotai/kimi-k3"
        if key:
            lines = upsert(lines, "NVIDIA_API_KEY", key)
            lines = upsert(lines, "NVIDIA_MODEL", model)
    if choice in {"2", "3"}:
        key = getpass.getpass("OPENAI_API_KEY (saisie masquée) : ").strip()
        model = input("Modèle OpenAI [gpt-5.6-luna] : ").strip() or "gpt-5.6-luna"
        if key:
            lines = upsert(lines, "OPENAI_API_KEY", key)
            lines = upsert(lines, "OPENAI_MODEL", model)
    lines = upsert(lines, "CADUCEUS_ENABLE_LLM_ARBITRATION", "1")
    lines = upsert(lines, "CADUCEUS_LLM_PROVIDER", "AUTO")
    ENV.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Configuration enregistrée dans {ENV}")
    print("Redémarrez CADUCEUS pour appliquer les changements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

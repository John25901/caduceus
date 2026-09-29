from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _default_caduceus_home() -> Path:
    """Persistent application data independent from the source ZIP/folder."""
    explicit = os.getenv("CADUCEUS_HOME")
    if explicit:
        return Path(explicit).expanduser()
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:  # Windows
        return Path(local_appdata) / "CADUCEUS"
    return Path.home() / ".caduceus"


CADUCEUS_HOME = _default_caduceus_home()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in {None, ""} else default


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    app_data_root: Path = Path(os.getenv("CADUCEUS_HOME", CADUCEUS_HOME))

    # Versioned source-of-truth shipped/managed with the application.
    camcis_path: Path = Path(os.getenv("CADUCEUS_CAMCIS_PATH", PROJECT_ROOT / "data" / "reference" / "Code_SH_CAMCIS.xlsx"))
    validated_cases_path: Path = Path(os.getenv("CADUCEUS_VALIDATED_CASES_PATH", PROJECT_ROOT / "data" / "validated_cases"))
    user_validated_cases_path: Path = Path(os.getenv("CADUCEUS_USER_VALIDATED_CASES", CADUCEUS_HOME / "runtime" / "validated_cases_user.csv"))

    # Durable runtime state: survives extraction of a new source ZIP.
    audit_db_path: Path = Path(os.getenv("CADUCEUS_AUDIT_DB", CADUCEUS_HOME / "runtime" / "caduceus_audit.db"))
    metrics_db_path: Path = Path(os.getenv("CADUCEUS_METRICS_DB", CADUCEUS_HOME / "runtime" / "caduceus_metrics.db"))
    qdrant_path: Path = Path(os.getenv("CADUCEUS_QDRANT_PATH", CADUCEUS_HOME / "qdrant_storage"))
    index_manifest_path: Path = Path(os.getenv("CADUCEUS_INDEX_MANIFEST", CADUCEUS_HOME / "runtime" / "camcis_index_manifest.json"))
    reference_state_path: Path = Path(os.getenv("CADUCEUS_REFERENCE_STATE", CADUCEUS_HOME / "runtime" / "reference_state.json"))
    benchmark_cache_path: Path = Path(os.getenv("CADUCEUS_BENCHMARK_CACHE", CADUCEUS_HOME / "runtime" / "benchmark_cache"))
    fx_cache_path: Path = Path(os.getenv("CADUCEUS_FX_CACHE", CADUCEUS_HOME / "runtime" / "fx_rates.json"))
    llm_cache_path: Path = Path(os.getenv("CADUCEUS_LLM_CACHE", CADUCEUS_HOME / "runtime" / "caduceus_llm_cache.db"))

    # Logical collection prefix. Physical Qdrant collections are versioned by CAMCIS hash + model hash.
    qdrant_collection: str = os.getenv("CADUCEUS_QDRANT_COLLECTION", "camcis_tariff_v2")
    embedding_model: str = os.getenv("CADUCEUS_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    enable_semantic: bool = _env_bool("CADUCEUS_ENABLE_SEMANTIC", True)
    auto_sync_index: bool = _env_bool("CADUCEUS_AUTO_SYNC_INDEX", True)
    embedding_batch_size: int = _env_int("CADUCEUS_EMBEDDING_BATCH_SIZE", 128)
    keep_old_indexes: bool = _env_bool("CADUCEUS_KEEP_OLD_INDEXES", False)

    auto_accept_score: float = float(os.getenv("CADUCEUS_AUTO_ACCEPT_SCORE", "0.82"))
    min_margin: float = float(os.getenv("CADUCEUS_MIN_MARGIN", "0.08"))

    # Sprint 6 — arbitrage LLM contrôlé. Aucun modèle n'est autorisé à inventer un code SH :
    # il choisit uniquement dans la liste fermée de candidats CAMCIS ou s'abstient.
    enable_llm_arbitration: bool = _env_bool("CADUCEUS_ENABLE_LLM_ARBITRATION", True)
    llm_provider: str = os.getenv("CADUCEUS_LLM_PROVIDER", "AUTO")
    llm_timeout_seconds: int = _env_int("CADUCEUS_LLM_TIMEOUT_SECONDS", 45)
    llm_max_calls_per_dossier: int = _env_int("CADUCEUS_MAX_LLM_CALLS_PER_DOSSIER", 25)
    llm_min_confidence: float = float(os.getenv("CADUCEUS_LLM_MIN_CONFIDENCE", "0.70"))
    llm_min_retrieval_score: float = float(os.getenv("CADUCEUS_LLM_MIN_RETRIEVAL_SCORE", "0.35"))

    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "moonshotai/kimi-k3")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    # Benchmarks are NEVER launched on startup. These models are only evaluated on explicit command.
    benchmark_models_csv: str = os.getenv(
        "CADUCEUS_BENCHMARK_MODELS",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2,intfloat/multilingual-e5-small",
    )

    @property
    def benchmark_models(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in self.benchmark_models_csv.split(",") if x.strip())


settings = Settings()

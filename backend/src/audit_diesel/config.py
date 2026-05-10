"""Paths, constantes globais e settings via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz de codigo: .../backend
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = BACKEND_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
DB_PATH: Path = DATA_DIR / "audit.db"

# Nomes canonicos dos arquivos de entrada (com espacos como o cliente envia).
CHECKLIST_FILENAME: str = "listagem_de_chamados___recebimento_de_diesel_ARCO JP.xlsx"
MOBILIZADOS_FILENAME: str = "relatorio_mobilizados_ARCO JP.xlsx"
INFLEET_FILENAME: str = "Infleet - Abastecimentos_ARCO JP.xlsx"

# Tolerancia da regra §4.4 do escopo: |diferenca| < 2% para aprovar.
TOLERANCIA_PERCENTUAL: float = 0.02

# Z-score limite para o alerta de outlier de consumo.
OUTLIER_ZSCORE_LIMITE: float = 3.0
OUTLIER_MIN_HISTORICO: int = 5


class Settings(BaseSettings):
    """Settings carregaveis do .env / variaveis de ambiente.

    A camada de IA usa um provider OpenAI-compatible escolhido em runtime via
    `LLM_PROVIDER`. Se a chave nao estiver disponivel ou `AUDIT_AI_OFFLINE=1`,
    o sistema usa fixtures determinisitcas.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider config (OpenAI-compatible API).
    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str | None = None
    llm_model: str = "qwen/qwen3-32b"
    llm_fallback_model: str | None = None
    llm_request_timeout_s: float = 60.0
    llm_max_retries: int = 3

    # Forca o uso de fixtures mesmo se a chave estiver presente.
    audit_ai_offline: bool = False

    # Modo demonstracao para a apresentacao:
    #   "off"     -> sem cache (default).
    #   "record"  -> chama o provider normalmente e grava cada resposta no
    #                diretorio demo_cache (popula o cache para a demo).
    #   "true"    -> le do demo_cache; se nao houver entrada, cai pro provider
    #                (idealmente offline) e grava silenciosamente.
    # Garante respostas instantaneas e identicas durante a apresentacao,
    # imune a quedas da internet ou variacao de latencia da API externa.
    demo_mode: str = "off"
    demo_cache_dir: str = "data/demo_cache"

    # CORS para o front Next.js local.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def demo_cache_path(self) -> Path:
        return BACKEND_DIR / self.demo_cache_dir

    @property
    def demo_replay(self) -> bool:
        """True se o cache deve ser lido (modo apresentacao)."""
        return self.demo_mode.lower() in {"true", "replay", "1", "on"}

    @property
    def demo_record(self) -> bool:
        """True se o cache deve ser populado a partir das chamadas reais."""
        return self.demo_mode.lower() == "record"


def get_settings() -> Settings:
    """Retorna instancia de Settings carregada do ambiente / .env."""
    return Settings()


def db_url(path: Path | None = None) -> str:
    """Monta URL SQLite para SQLModel."""
    p = path or DB_PATH
    return f"sqlite:///{p}"

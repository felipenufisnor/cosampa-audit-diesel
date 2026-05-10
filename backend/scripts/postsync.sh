#!/usr/bin/env bash
# Workaround macOS: uv marca .pth files com UF_HIDDEN, o que faz o site.py
# ignora-los, quebrando a editable install. Rode apos `uv sync` quando o
# `audit-diesel` reclamar que `audit_diesel` nao foi encontrado.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${HERE}/.venv"
if [[ -d "${VENV}" ]]; then
  find "${VENV}" -name "*.pth" -exec chflags nohidden {} + 2>/dev/null || true
  echo "OK: .pth files no .venv estao visiveis."
else
  echo "Aviso: ${VENV} nao existe. Rode 'uv sync' primeiro."
fi

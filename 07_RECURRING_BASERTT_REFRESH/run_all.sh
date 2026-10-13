#!/usr/bin/env bash
set -euo pipefail
REFRESH_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
: "${NS3_DIR:?Set NS3_DIR to a dedicated, clean course ns-3.48 tree. See README.md.}"
command -v uv >/dev/null || { echo "uv is required for the locked Python environment. See README.md." >&2; exit 1; }
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$REFRESH_ROOT/.venv}"
uv sync --frozen --project "$REFRESH_ROOT/code"
exec uv run --frozen --project "$REFRESH_ROOT/code" python "$REFRESH_ROOT/code/experiments.py" run --ns3 "$NS3_DIR" "$@"

#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Collect MPAS forecast outputs
# =============================================================================
#
# Usage:
#
#   scripts/08_collect_forecast_outputs.sh CYCLE RUN_DIR
#
# Example:
#
#   scripts/08_collect_forecast_outputs.sh \
#     2018041421 \
#     /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/runs/test48h_x1.10242_2018041421_np64
#
# This creates:
#
#   /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/forecasts/CYCLE/f024.nc
#   /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/forecasts/CYCLE/f048.nc
#
# =============================================================================

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 CYCLE RUN_DIR"
  echo
  echo "CYCLE format: YYYYMMDDHH"
  exit 1
fi

CYCLE="$1"
RUN_DIR="$2"

DATA_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global
OUT_DIR="${DATA_ROOT}/forecasts/${CYCLE}"

if [[ ! "${CYCLE}" =~ ^[0-9]{10}$ ]]; then
  echo "ERRO: CYCLE deve estar no formato YYYYMMDDHH: ${CYCLE}"
  exit 1
fi

if [[ ! -d "${RUN_DIR}" ]]; then
  echo "ERRO: RUN_DIR não existe:"
  echo "  ${RUN_DIR}"
  exit 1
fi

mkdir -p "${OUT_DIR}"

YYYY=${CYCLE:0:4}
MM=${CYCLE:4:2}
DD=${CYCLE:6:2}
HH=${CYCLE:8:2}

read -r F024_TIME F048_TIME < <(
python3 - <<PY
from datetime import datetime, timedelta

cycle = datetime.strptime("${YYYY}${MM}${DD}${HH}", "%Y%m%d%H")
f024 = cycle + timedelta(hours=24)
f048 = cycle + timedelta(hours=48)

fmt = "%Y-%m-%d_%H.00.00"
print(f024.strftime(fmt), f048.strftime(fmt))
PY
)

F024_SRC="${RUN_DIR}/restart.${F024_TIME}.nc"
F048_SRC="${RUN_DIR}/restart.${F048_TIME}.nc"

for f in "${F024_SRC}" "${F048_SRC}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERRO: arquivo não encontrado:"
    echo "  ${f}"
    echo
    echo "Arquivos restart disponíveis em RUN_DIR:"
    ls -lh "${RUN_DIR}"/restart*.nc 2>/dev/null || true
    exit 1
  fi
done

ln -sfn "${F024_SRC}" "${OUT_DIR}/f024.nc"
ln -sfn "${F048_SRC}" "${OUT_DIR}/f048.nc"

cat > "${OUT_DIR}/metadata.txt" <<META
cycle=${CYCLE}
cycle_iso=${YYYY}-${MM}-${DD}_${HH}:00:00
run_dir=${RUN_DIR}
f024_source=${F024_SRC}
f048_source=${F048_SRC}
f024_valid=${F024_TIME}
f048_valid=${F048_TIME}
created_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
META

echo "Collected forecast outputs:"
echo "${OUT_DIR}"
ls -lh "${OUT_DIR}"

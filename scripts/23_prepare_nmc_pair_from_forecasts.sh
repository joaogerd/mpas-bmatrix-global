#!/usr/bin/env bash
set -euo pipefail

# Stage one NMC pair from two MPAS forecast restart files.
# Expected pair:
#   older cycle f048 valid at VALID_TIME
#   newer cycle f024 valid at VALID_TIME

WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
MESH_NAME=${MESH_NAME:-x1.10242}
NPROC=${NPROC:-64}
CONFIG_DT=${CONFIG_DT:-60}

OLD_INIT_TIME=${OLD_INIT_TIME:?set OLD_INIT_TIME, for example 2026-06-11_00:00:00}
NEW_INIT_TIME=${NEW_INIT_TIME:?set NEW_INIT_TIME, for example 2026-06-12_00:00:00}
VALID_TIME=${VALID_TIME:?set VALID_TIME, for example 2026-06-13_00:00:00}

OLD_SAFE=${OLD_INIT_TIME//:/.}
NEW_SAFE=${NEW_INIT_TIME//:/.}
VALID_SAFE=${VALID_TIME//:/.}

OLD_RUN_ID=${OLD_RUN_ID:-forecast_${MESH_NAME}_${OLD_SAFE}_f048_dt${CONFIG_DT}_np${NPROC}}
NEW_RUN_ID=${NEW_RUN_ID:-forecast_${MESH_NAME}_${NEW_SAFE}_f024_dt${CONFIG_DT}_np${NPROC}}

F048_FILE=${F048_FILE:-${WORK_ROOT}/runs/${OLD_RUN_ID}/restart.${VALID_SAFE}.nc}
F024_FILE=${F024_FILE:-${WORK_ROOT}/runs/${NEW_RUN_ID}/restart.${VALID_SAFE}.nc}

PAIR_ID=${PAIR_ID:-nmc_${MESH_NAME}_valid_${VALID_SAFE}}
PAIR_DIR=${PAIR_DIR:-${WORK_ROOT}/nmc_pairs/${PAIR_ID}}
ARCHIVE_DIR=${ARCHIVE_DIR:-${DATA_ROOT}/nmc_pairs/${PAIR_ID}}

for f in "${F048_FILE}" "${F024_FILE}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERRO: required forecast file not found: ${f}"
    exit 1
  fi
done

mkdir -p "${PAIR_DIR}" "${ARCHIVE_DIR}"

ln -sfn "${F048_FILE}" "${PAIR_DIR}/f048.nc"
ln -sfn "${F024_FILE}" "${PAIR_DIR}/f024.nc"
ln -sfn "${F048_FILE}" "${ARCHIVE_DIR}/f048.nc"
ln -sfn "${F024_FILE}" "${ARCHIVE_DIR}/f024.nc"

cat > "${PAIR_DIR}/pair.env" <<EOF
MESH_NAME=${MESH_NAME}
NPROC=${NPROC}
CONFIG_DT=${CONFIG_DT}
OLD_INIT_TIME=${OLD_INIT_TIME}
NEW_INIT_TIME=${NEW_INIT_TIME}
VALID_TIME=${VALID_TIME}
OLD_RUN_ID=${OLD_RUN_ID}
NEW_RUN_ID=${NEW_RUN_ID}
F048_FILE=${F048_FILE}
F024_FILE=${F024_FILE}
PAIR_ID=${PAIR_ID}
PAIR_DIR=${PAIR_DIR}
ARCHIVE_DIR=${ARCHIVE_DIR}
EOF

cp "${PAIR_DIR}/pair.env" "${ARCHIVE_DIR}/pair.env"

cat > "${PAIR_DIR}/README.md" <<EOF
# NMC pair ${PAIR_ID}

This directory stages one NMC pair for MPAS-JEDI background-error processing.

- f048.nc: forecast initialized at ${OLD_INIT_TIME}, valid at ${VALID_TIME}
- f024.nc: forecast initialized at ${NEW_INIT_TIME}, valid at ${VALID_TIME}

Both files are symbolic links to the forecast restart files.
EOF

cp "${PAIR_DIR}/README.md" "${ARCHIVE_DIR}/README.md"

echo "SUCCESS: NMC pair staged."
echo "PAIR_DIR=${PAIR_DIR}"
echo "ARCHIVE_DIR=${ARCHIVE_DIR}"
echo
ls -lh "${PAIR_DIR}/f048.nc" "${PAIR_DIR}/f024.nc" "${PAIR_DIR}/pair.env"
#!/usr/bin/env bash
set -euo pipefail

GRAPH_DIR=/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/graph
GRAPH_FILE=x1.10242.graph.info
NPROC=${1:-64}

cd "${GRAPH_DIR}"

echo "Working directory: $(pwd)"
echo "Graph file: ${GRAPH_FILE}"
echo "NPROC: ${NPROC}"

if ! command -v gpmetis >/dev/null 2>&1; then
  echo "ERRO: gpmetis não encontrado. Rode:"
  echo "  source /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global/scripts/load_jaci_env.sh"
  exit 1
fi

if [[ ! -f "${GRAPH_FILE}" ]]; then
  echo "ERRO: arquivo de grafo não encontrado: ${GRAPH_FILE}"
  exit 1
fi

OUT="${GRAPH_FILE}.part.${NPROC}"

if [[ -f "${OUT}" ]]; then
  echo "Partição já existe: ${OUT}"
  ls -lh "${OUT}"
  exit 0
fi

echo "Running gpmetis..."
gpmetis "${GRAPH_FILE}" "${NPROC}"

echo
echo "Generated:"
ls -lh "${OUT}"

echo
echo "Preview:"
head "${OUT}"

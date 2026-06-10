#!/usr/bin/env bash
# =============================================================================
# Load JACI MPAS-JEDI environment
# =============================================================================
#
# This script must be sourced:
#
#   source scripts/load_jaci_env.sh
#
# It loads the spack-stack/JACI environment needed for:
#   - mpas_atmosphere
#   - mpas_init_atmosphere
#   - mpasjedi_error_covariance_toolbox.x
#   - gpmetis
#   - ncdump
#   - Cray MPICH/libfabric runtime
#
# =============================================================================

# Não usar set -euo pipefail aqui, pois este script é "sourced"
# e isso afetaria o shell interativo do usuário.

# Salva o diretório de onde o usuário chamou o script

__JACI_ENV_OLDPWD="$(pwd)"

module --force purge 2>/dev/null || module purge

export STACK_ROOT=/p/projetos/monan_das/joao.gerd/work/spack-stack-inpe-overlay-20260515T181917Z/spack-stack
export STACK_ENV_NAME=jaci-mpas-jedi-gcc12-craympich
export STACK_MODULE_ROOT=${STACK_ROOT}/envs/${STACK_ENV_NAME}/modules
export STACK_SITE_SETUP=configs/sites/tier2/jaci/setup.sh
export STACK_ENV_MODULE=cray-mpich/8.1.31/none/none/jedi-mpas-env/1.0.0

cd "${STACK_ROOT}"
source "${STACK_SITE_SETUP}"

module use "${STACK_MODULE_ROOT}"
module load "${STACK_ENV_MODULE}"

# Volta para o diretório original
cd "${__JACI_ENV_OLDPWD}" || return 1
unset __JACI_ENV_OLDPWD

echo "Loaded JACI MPAS-JEDI environment"
echo "STACK_ROOT=${STACK_ROOT}"
echo "STACK_ENV_NAME=${STACK_ENV_NAME}"
echo "STACK_ENV_MODULE=${STACK_ENV_MODULE}"
echo "PWD=$(pwd)"

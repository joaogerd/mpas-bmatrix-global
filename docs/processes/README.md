# Processos do workflow da matriz B MPAS-JEDI/SABER

Este diretório documenta, em arquivos separados, os processos usados no workflow de geração, calibração e validação da matriz B global do MPAS-JEDI/SABER no JACI.

A cadeia operacional validada no repositório é:

```text
NMC -> BFLOW -> VBAL -> HDIAG -> NICAS -> SO -> DIRAC
```

No código atual, `NMC` gera ou organiza os pares de previsões `f048` e `f024`; `BFLOW` transforma esses pares em amostras `PTB_f48mf24.nc`; `VBAL`, `HDIAG` e `NICAS` calibram os componentes estatísticos da B; `SO` e `DIRAC` validam a B pronta, respectivamente em um teste variacional com observação sintética e em um teste de impulso.

## Tabela geral

| Processo | Documento | Função curta | Depende de | Produto principal |
|---|---|---|---|---|
| BFLOW | [bflow.md](bflow.md) | Prepara as amostras estatísticas `PTB_f48mf24.nc` usadas pela calibração da B. | Forecasts MPAS `f048` e `f024`, pesos ESMF, NCL, NCO e NetCDF. | `output/YYYYMMDDHH/PTB_f48mf24.nc`, `manifest.tsv` |
| NMC | [nmc.md](nmc.md) | Gera ou organiza pares NMC válidos no mesmo horário, usando previsões de 48h e 24h. | WPS/init MPAS, forecasts MPAS, `mpaswf`. | `f048.nc`, `f024.nc`, opcionalmente `nmc_diff_f048_minus_f024.nc` |
| VBAL | [vbal.md](vbal.md) | Calibra o balanço vertical e multivariado via `BUMP_VerticalBalance`. | Amostras BFLOW/NMC. | `mpas_vbal.nc`, `mpas_sampling.nc`, produtos locais |
| HDIAG | [hdiag.md](hdiag.md) | Calcula desvio padrão e escalas de correlação horizontal/vertical. | VBAL validado e amostras NMC. | `mpas.stddev.nc`, `mpas.cor_rh.nc`, `mpas.cor_rv.nc` |
| NICAS | [nicas.md](nicas.md) | Constrói o operador de correlação/localização BUMP/NICAS por variável e faz merge. | HDIAG validado, escalas `cor_rh`/`cor_rv`, malha e partição. | `merge/mpas_nicas.nc`, `mpas_nicas_local_*`, `mpas_nicas_grids_local_*` |
| SO | [so.md](so.md) | Testa a B completa em uma assimilação 3D-Var com observações sintéticas. | NICAS, StdDev/HDIAG, VBAL. | `obsout_SO_T.h5`, `obsout_SO_U.h5`, `an.*.nc` |
| DIRAC | [dirac.md](dirac.md) | Aplica impulso pontual e verifica a resposta da B completa. | NICAS, StdDev/HDIAG, VBAL. | `mpas.dirac.nc` |

## Ordem sugerida de leitura

1. [NMC](nmc.md), para entender a origem dos pares `f048`/`f024`.
2. [BFLOW](bflow.md), para entender como os pares viram perturbações `PTB_f48mf24.nc`.
3. [VBAL](vbal.md), para entender o balanço vertical/multivariado.
4. [HDIAG](hdiag.md), para entender `stddev`, `cor_rh` e `cor_rv`.
5. [NICAS](nicas.md), para entender a correlação espacial e o merge por variável.
6. [SO](so.md), para entender a validação variacional com observação única.
7. [DIRAC](dirac.md), para entender o teste de impulso da B completa.

## Dependência operacional resumida

```text
WPS/ungrib + MPAS init
  -> MPAS forecasts f024/f048
  -> NMC
  -> BFLOW
  -> VBAL
  -> HDIAG
  -> NICAS
  -> SO
  -> DIRAC
```

## Fontes analisadas no repositório

A documentação foi baseada principalmente nos seguintes arquivos:

- `configs/jaci-x1.10242.yaml`
- `pyproject.toml`
- `src/mpas_workflow/cli.py`
- `src/mpas_workflow/nmc.py`
- `src/mpas_workflow/bflow.py`
- `src/mpas_workflow/bcov.py`
- `src/mpas_workflow/bcov_pipeline.py`
- `src/mpas_workflow/forecast.py`
- `docs/tutorial_bmatrix.md`
- `docs/jaci-x1.10242-bmatrix-smoke.md`
- documentos e utilitários diagnósticos localizados por busca: `vbal_groups.py`, `hdiag_summary.py`, `nicas_summary.py`, `dirac_summary.py`, `pipeline-and-dirac-tools.md`, `bmatrix-smoke-vs-production.md`, `vbal-empty-product-note.md`.

Quando um valor não aparece explicitamente nesses arquivos, os documentos individuais registram a limitação como `não documentado no repositório` ou `não inferível a partir dos arquivos analisados`.

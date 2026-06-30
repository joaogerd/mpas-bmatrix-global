# Figuras da matriz B para apresentação

Este comando produz um conjunto curto de figuras científicas para apresentação a partir da primeira matriz B diagnosticada no JACI. Os PNGs têm fundo transparente, texto cinza-escuro, grade cinza-clara e acentos azul, verde-água, laranja e magenta, para inserção direta nos slides.

## Escopo científico

Os quatro produtos resumem componentes complementares da matriz estática:

```text
B = K1 K2 Sigma C Sigma^T K2^T K1^T
```

1. `01_bmatrix_balance_explained_variance.png`: fração da variância de `temperature`, `velocity_potential` e `surface_pressure` explicada por `stream_function` em latitude × nível.
2. `02_bmatrix_temperature_psi_regression.png`: matriz de regressão vertical de `temperature` sobre `stream_function` na latitude próxima de 35°.
3. `03_bmatrix_stddev_and_correlation_scales.png`: perfis médios de desvios-padrão e escalas de correlação horizontal e vertical de `stream_function`, `velocity_potential`, `temperature` e `spechum`.
4. `04_bmatrix_dirac_temperature_response.png`: resposta espacial da B completa a um impulso de temperatura em três níveis próximos ao nível selecionado.

As duas primeiras figuras correspondem aos diagnósticos de balanço VBAL. A terceira resume os parâmetros HDIAG usados por NICAS. A quarta é um teste DIRAC da B completa, isto é, da composição NICAS + StdDev + VBAL + Control2Analysis.

> **Cuidado:** o caso `np128_2026061000_2026061300` é o baseline/smoke inicial, com poucos membros. As figuras servem para demonstrar estrutura, consistência e capacidade diagnóstica da cadeia; não devem ser descritas como estatística final de produção.

## Dependência

`matplotlib>=3.8` é dependência de execução do projeto.

## Caso inicial x1.10242

```bash
source scripts/load_jaci_env.sh
conda activate mpaswf

VBAL=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/vbal/np128_2026061000_2026061300
HDIAG=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/hdiag/np128_2026061000_2026061300
DIRAC=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/dirac/np128_2026061000_2026061300
OUT=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/figures_presentation_np128_2026061000_2026061300

PYTHONPATH="$PWD/src" python -m mpas_workflow.bmatrix_presentation \
  --vbal-workspace "$VBAL" \
  --hdiag-workspace "$HDIAG" \
  --dirac-workspace "$DIRAC" \
  --output-dir "$OUT" \
  --latitude 35 \
  --level 15 \
  --dpi 300
```

O código procura automaticamente `latCell` e `lonCell` no workspace DIRAC, no caminho HDIAG registrado em `README.md` e no workspace irmão `covariance/hdiag/<nome-do-caso>`. Ele só aceita um arquivo de coordenadas com o mesmo número de células que a resposta DIRAC.

Caso necessário, informe o NetCDF da malha explicitamente por `--coordinates-file`. O diretório de saída também recebe um `README.md` identificando os workspaces empregados.

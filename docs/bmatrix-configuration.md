# Configuração científica da matriz B

## Objetivo

O workflow separa dois tipos de configuração:

```text
configs/jaci-x1.10242.yaml
  ambiente, caminhos, malha, partição MPI, PBS e executáveis

configs/bmatrix-x1.10242.yaml
  variáveis da B, nomes canônicos, nomes NetCDF, VBAL, HDIAG,
  NICAS, DIRAC e teste de observação única
```

A separação evita que uma alteração científica exija modificar `bcov.py`.

## Contrato `code` × `file`

Cada variável de controle é declarada uma única vez no bloco `controls`:

```yaml
controls:
  - code: air_temperature
    file: temperature
    dimensions: 3d
```

- `code` é o nome lógico e canônico usado pelo MPAS-JEDI/SABER.
- `file` é o nome físico que existe nos PTBs BFLOW e no NetCDF MPAS.
- `dimensions` informa se a variável pertence ao grupo tridimensional (`3d`) ou ao grupo de superfície (`2d`) do BUMP/NICAS.

Para a configuração atual, o contrato é:

| Nome canônico MPAS-JEDI | Campo físico no NetCDF |
| --- | --- |
| `air_horizontal_streamfunction` | `stream_function` |
| `air_horizontal_velocity_potential` | `velocity_potential` |
| `air_temperature` | `temperature` |
| `water_vapor_mixing_ratio_wrt_moist_air` | `spechum` |
| `air_pressure_at_surface` | `surface_pressure` |

O wrapper gera aliases somente onde é necessário ler os PTBs físicos durante a calibração. VBAL, HDIAG e NICAS passam a operar com os nomes canônicos como variáveis internas SABER.

## Uso

Após atualizar o repositório, reinstale em modo editável:

```bash
source scripts/load_jaci_env.sh
conda activate mpaswf
python -m pip install -e .
```

O comando habitual passa a carregar automaticamente o contrato configurado:

```bash
mpasbcov vbal-prepare \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL" \
  --clean
```

O entry point anterior continua disponível apenas para comparação de resultados legados:

```bash
mpasbcov-legacy vbal-prepare \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL_LEGACY" \
  --clean
```

## Resultado esperado

O YAML gerado para VBAL deve declarar:

```yaml
state variables:
- air_horizontal_streamfunction
- air_horizontal_velocity_potential
- air_temperature
- water_vapor_mixing_ratio_wrt_moist_air
- air_pressure_at_surface
```

e as relações de balanço devem usar somente a nomenclatura canônica:

```yaml
vertical balance:
  vbal:
  - balanced variable: air_horizontal_velocity_potential
    unbalanced variable: air_horizontal_streamfunction
  - balanced variable: air_temperature
    unbalanced variable: air_horizontal_streamfunction
  - balanced variable: air_pressure_at_surface
    unbalanced variable: air_horizontal_streamfunction
```

Após gerar a B com esse contrato, o YAML de 3DVar/3D-FGAT deve declarar os mesmos nomes em `active variables` e em `Control2Analysis`. Não deve ser necessário manter aliases específicos para `BUMP_NICAS` ou para grupos compostos do `BUMP_VerticalBalance`.

## Parâmetros movidos para o YAML científico

O arquivo `bmatrix-x1.10242.yaml` concentra:

- nomes canônicos e físicos das variáveis de controle;
- dimensões 3d/2d e agrupamento NICAS;
- relações de balanço vertical/multivariado;
- parâmetros de amostragem do VBAL;
- mínimo de membros, variância, ajuste e parâmetros HDIAG;
- resolução, tamanho máximo de grade e pontos internos Dirac do NICAS;
- posições, variável e índice do teste DIRAC;
- variáveis, observações sintéticas e variantes do teste SO.

Portanto, valores como `dominant_mode`, escalas horizontais, número de classes de distância, resolução NICAS, locais Dirac e observações do SO devem ser alterados no YAML, não no Python.

## Quando regenerar a matriz

| Alteração | Regeneração necessária |
| --- | --- |
| `controls`, `dimensions` ou mapeamento `code`/`file` | BFLOW → VBAL → HDIAG → NICAS → SO → DIRAC |
| `vbal.relations`, `vbal.sampling`, `pseudo_inverse` ou `dominant_mode` | VBAL → HDIAG → NICAS → SO → DIRAC |
| `hdiag.*` | HDIAG → NICAS → SO → DIRAC |
| `nicas.*` | NICAS → SO → DIRAC |
| `dirac.*` | somente DIRAC |
| `single_observation.*` | somente SO |
| malha, `nproc`, arquivos estáticos ou `geovars.yaml` | BFLOW → VBAL → HDIAG → NICAS → SO → DIRAC |

## Compatibilidade

Uma B já produzida com a versão anterior contém nomes físicos nos produtos VBAL/NICAS, incluindo grupos compostos como:

```text
stream_function-temperature
stream_function-velocity_potential
```

Ela continua utilizável pelo modo `mpasbcov-legacy` ou por um YAML que possua aliases de leitura. Ela **não** deve ser considerada equivalente a uma B nova gerada com o contrato canônico.

Para remover os aliases da configuração de assimilação, regenere a cadeia a partir do VBAL com o novo `mpasbcov` e valide, nesta ordem:

```text
VBAL → HDIAG → NICAS → SO → DIRAC → 3DVar → 3DVar-FGAT
```

## Verificações mínimas

```bash
# O YAML deve mostrar variáveis canônicas para SABER.
grep -E 'air_horizontal|air_temperature|water_vapor_mixing' \
  "$VBAL/VBAL/run_vbal.yaml"

# O stream de controle continua mostrando os nomes físicos do NetCDF.
cat "$VBAL/VBAL/stream_list.atmosphere.control"

# SO e DIRAC devem funcionar com active variables canônicas.
grep -A7 'active variables' "$SO/run_SO.yaml"
grep -A7 'active variables' "$DIRAC/run_dirac.yaml"
```

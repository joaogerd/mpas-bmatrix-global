# `mpasso`

## Para que serve

`mpasso` prepara, executa e valida testes de observação única (*single observation*) usando a matriz B construída pelo workflow.

O objetivo é avaliar se a matriz B produz incrementos fisicamente coerentes e espacialmente consistentes quando uma observação sintética é assimilada.

## Papel no workflow da matriz B

A etapa SO é uma validação da matriz B, não uma etapa de treinamento. Ela usa os produtos de VBAL, HDIAG e NICAS para montar uma configuração 3D-Var simples com uma ou mais observações sintéticas.

## Teoria usada

Um teste de observação única injeta uma única observação em uma posição e nível conhecidos. A resposta do sistema mostra como a matriz B espalha a informação no espaço, na vertical e entre variáveis.

Se a B estiver coerente, o incremento tende a apresentar:

- estrutura espacial suave;
- escala horizontal compatível com a correlação estimada;
- estrutura vertical coerente;
- relações multivariadas esperadas;
- ausência de ruído ou padrões numéricos espúrios.

## Entradas

- Workspace NICAS validado.
- Workspace HDIAG validado.
- Workspace VBAL validado.
- Arquivos:
  - `mpas_nicas.nc`
  - `mpas_nicas_local_*.nc`
  - `mpas.stddev.nc`
  - `mpas_vbal.nc`
  - `mpas_vbal_local_*.nc`
- Template/background MPAS completo.
- Executável `mpasjedi_variational.x`.

## Saídas

No workspace SO:

```text
run_SO.yaml
qsub_so.bash
run_SO.runlog
stdout.log
stderr.log
an.*.nc
obsout_SO_T.h5
obsout_SO_U.h5
bg_so.nc
```

Para variantes:

```text
run_SO_t_only.yaml
run_SO_u_only.yaml
```

## Como funciona internamente

A implementação está em `src/mpas_workflow/so_core/`:

- `model.py`: nomes de artefatos e variantes;
- `static.py`: background SO e links de suporte;
- `config_files.py`: YAML e PBS;
- `prepare.py`: montagem do workspace;
- `jobs.py`: submissão e retry;
- `checks.py`: validação;
- `cli.py`: CLI.

## Comandos principais

Preparar SO padrão:

```bash
mpasso prepare \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace /path/to/nicas_workspace \
  --hdiag-workspace /path/to/hdiag_workspace \
  --vbal-workspace /path/to/vbal_workspace \
  --clean
```

Submeter:

```bash
mpasso submit --workspace /path/to/so_workspace --wait
```

Validar:

```bash
mpasso validate --workspace /path/to/so_workspace
```

## Variantes

- `default`: observa temperatura e vento zonal.
- `t-only`: somente temperatura.
- `u-only`: somente vento zonal.

Exemplo:

```bash
mpasso prepare --nicas-workspace $NICAS --variant t-only
mpasso submit --workspace $SO --variant t-only --wait
```

## Validação

A validação confere:

- status final de sucesso;
- arquivo de análise `an.*.nc`;
- arquivos `obsout` esperados para a variante;
- ausência de status final diferente de zero nos logs.

## Problemas comuns

- Background SO sem variáveis derivadas esperadas.
- `air_pressure`, `air_temperature` ou ventos físicos ausentes.
- Incompatibilidade entre variáveis de análise e variáveis do background.
- Produtos NICAS/VBAL incompletos.
- Falha do operador de observação por coordenada vertical ausente.

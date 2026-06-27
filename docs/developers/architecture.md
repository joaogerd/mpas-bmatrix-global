# Arquitetura do projeto

## Objetivo

Este documento descreve a arquitetura interna do `mpas-bmatrix-global` após a separação por responsabilidades.

O objetivo da arquitetura é manter cada etapa do workflow isolada, testável e fácil de evoluir.

## Princípio central

Cada ferramenta possui um pacote próprio:

```text
mpas_core/
bflow_core/
vbal_core/
hdiag_core/
nicas_core/
so_core/
validation/
```

Cada pacote segue, sempre que aplicável, a mesma organização:

```text
model.py         # constantes, estruturas e paths conceituais
workspace.py     # resolução de diretórios
static.py        # links e staging de arquivos estáticos
config_files.py  # geração de YAML/PBS/scripts auxiliares
prepare.py       # montagem do workspace
jobs.py          # submissão PBS e retries
checks.py        # validação da etapa
runner.py        # fachada pública
cli.py           # interface de linha de comando
```

## Fluxo de execução

```text
CLI
 ↓
runner
 ↓
prepare / jobs / checks
 ↓
workspace / config_files / static / model
 ↓
shell / NetCDF / PBS / executáveis MPAS-JEDI
```

## Responsabilidades

### `cli.py`

Responsável apenas por:

- parsing de argumentos;
- chamada da função adequada;
- retorno de código de saída.

Não deve conter lógica científica ou lógica de montagem de arquivos.

### `runner.py`

Fachada simples para uso programático. Deve agregar funções principais, mas não concentrar implementação pesada.

### `prepare.py`

Monta o workspace da etapa. Pode chamar:

- `workspace.py`;
- `static.py`;
- `config_files.py`;
- validações de pré-condição.

### `jobs.py`

Submete jobs PBS, aguarda execução quando solicitado e aplica retries quando necessário.

### `checks.py` ou `validate.py`

Valida produtos, logs e completude da etapa.

### `config_files.py`

Gera YAMLs, scripts PBS e scripts auxiliares.

### `static.py`

Cuida de links simbólicos, cópias e staging de arquivos necessários.

### `model.py`

Define nomes, constantes, estruturas de dados e funções de path que não dependem de execução.

## Regras de manutenção

- Não criar novos monólitos.
- Não colocar lógica de negócio em `cli.py`.
- Não duplicar YAMLs grandes em vários módulos.
- Não codificar paths absolutos fora de `configs/*.yaml`.
- Toda ferramenta nova deve ter documentação em `docs/tools/`.
- Todo produto novo deve ser documentado em `docs/products/`.
- Toda mudança científica deve ser explicada em `docs/theory/` ou no documento da ferramenta.

## Fluxo para adicionar nova etapa

1. Criar pacote `nova_etapa_core/`.
2. Criar `model.py`, `workspace.py`, `prepare.py`, `jobs.py`, `checks.py`, `cli.py`.
3. Registrar comando no `pyproject.toml`.
4. Adicionar documentação em `docs/tools/`.
5. Adicionar produtos em `docs/products/`, se houver.
6. Adicionar testes.

## Validação arquitetural

Antes de abrir PR ou mergear:

```bash
python -m pytest
mpasforecast --help
mpasbflow --help
mpasvbal --help
mpashdiag --help
mpasnicas --help
mpasso --help
mpasverify --help
```

## Estado dos legados

Os monólitos legados `bcov.py` e `forecast.py` foram removidos. A implementação oficial está nos pacotes `*_core`.

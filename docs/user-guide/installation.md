# Instalação do ambiente `mpaswf`

Este documento descreve a instalação do ambiente Python usado pelo workflow de geração da matriz B global MPAS-JEDI.

## Objetivo

Criar um ambiente único e reprodutível para executar as ferramentas:

- `mpasforecast`
- `mpasbflow`
- `mpasvbal`
- `mpashdiag`
- `mpasnicas`
- `mpasso`
- `mpasverify`

A regra do projeto é: **Conda/Mamba instala o ambiente científico completo; `pip` instala apenas o código local do repositório.**

## Pré-requisitos

- Acesso ao repositório `mpas-bmatrix-global`.
- Ambiente Conda ou Mamba disponível.
- Acesso aos executáveis MPAS-JEDI/SABER definidos no arquivo de configuração.
- Arquivos estáticos da malha MPAS disponíveis.

No JACI, carregue o Conda conforme o procedimento local:

```bash
module load anaconda
start_conda
```

## Instalação recomendada

A partir da raiz do repositório:

```bash
mamba env create -f environment.yml
conda activate mpaswf
```

Se o ambiente já existir:

```bash
mamba env update -n mpaswf -f environment.yml
conda activate mpaswf
```

Caso `mamba` não esteja disponível, use:

```bash
conda env update -n mpaswf -f environment.yml
conda activate mpaswf
```

## Instalação editável do pacote

O `environment.yml` instala o pacote local em modo editável. Para reinstalar manualmente:

```bash
pip install -e .
```

## Dependências críticas

O backend Python do BFLOW usa:

- `netCDF4` para leitura e escrita NetCDF;
- `xarray` para validação e comparação;
- `windspharm`/`pyspharm` para a conversão `u/v -> stream_function/velocity_potential`;
- `numpy` para operações numéricas.

`windspharm` depende de `pyspharm`, que é compilado. Por isso a instalação suportada é via `conda-forge`, não via `pip` isolado.

## Teste da instalação

```bash
python -c "from windspharm.standard import VectorWind; print('windspharm OK')"
mpasforecast --help
mpasbflow --help
mpasvbal --help
mpashdiag --help
mpasnicas --help
mpasso --help
mpasverify --help
```

## Atualização após mudanças no código

```bash
git pull
pip install -e .
python -m pytest
```

## Arquivo de configuração

O workflow usa, por padrão:

```text
configs/jaci-x1.10242.yaml
```

Esse arquivo define caminhos de instalação, dados estáticos, malha, fila PBS, diretórios de trabalho e parâmetros de execução.

Veja também: `docs/reference/configuration.md`.

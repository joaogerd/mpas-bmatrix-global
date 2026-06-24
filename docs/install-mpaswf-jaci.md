# Instalação do ambiente Python `mpaswf` no JACI

## 1. Finalidade

O ambiente `mpaswf` reúne as dependências Python e os comandos de linha de comando usados pelo workflow de geração da matriz B.

> **Ordem de carregamento no JACI.** Em sessões de trabalho, carregue primeiro o ambiente JACI e só então inicialize e ative o Conda. Isso reduz conflitos entre módulos e variáveis de ambiente definidos por `scripts/load_jaci_env.sh` e pelo Conda.

## 2. Dependências e comandos fornecidos

O repositório `mpas-bmatrix-global` contém ferramentas Python para preparar diretórios de trabalho, gerar YAMLs do JEDI/SABER, gerar scripts PBS, submeter jobs, validar saídas e criar diagnósticos.

Essas ferramentas precisam de um ambiente Python com bibliotecas como:

```text
PyYAML
numpy
netCDF4
cftime
xarray
```

Além disso, a instalação do pacote cria comandos de linha de comando, como:

```text
mpaswf
mpasbflow
mpasbcov
```

Esses comandos são usados ao longo do tutorial.

## 3. Criar e preparar o ambiente Conda

No JACI, carregue o módulo do Anaconda e inicialize o ambiente Conda:

```bash
module load anaconda
start_conda
```

Em seguida, crie o ambiente `mpaswf` com Python 3.11:

```bash
conda create -n mpaswf python=3.11 -y
```

Ative o ambiente criado:

```bash
conda activate mpaswf
```

Por fim, atualize o `pip` e instale as dependências Python necessárias:

```bash
python -m pip install --upgrade pip

python -m pip install \
  PyYAML \
  numpy \
  netCDF4 \
  cftime \
  xarray \
  matplotlib
```

> Nas próximas sessões de trabalho no repositório, use a seguinte ordem:
>
> ```bash
> cd /p/projetos/monan_das/${USER}/projects/mpas-bmatrix-global
> source scripts/load_jaci_env.sh
> module load anaconda
> start_conda
> conda activate mpaswf
> ```

A dependência `matplotlib` é necessária para os diagnósticos gráficos, mesmo que não esteja listada como dependência obrigatória principal no `pyproject.toml`.

## 4. Instalar o repositório

Entre no repositório:

```bash
cd /p/projetos/monan_das/${USER}/projects/mpas-bmatrix-global
```

Carregue o ambiente JACI e, em seguida, inicialize e ative o Conda:

```bash
source scripts/load_jaci_env.sh
module load anaconda
start_conda
conda activate mpaswf
```

Instale a ferramenta em modo editável:

```bash
python -m pip install -e .
```

Esse modo é recomendado durante o desenvolvimento porque alterações feitas no código passam a ser usadas imediatamente pelo ambiente.

## 5. Verificar instalação

Confira se os comandos foram instalados:

```bash
mpaswf --help
mpasbflow --help
mpasbcov --help
```

Resultado esperado:

```text
os três comandos devem imprimir suas opções de uso
não deve aparecer erro de comando não encontrado
```

---

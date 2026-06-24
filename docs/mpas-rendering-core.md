# Núcleo de renderização MPAS

Esta branch introduz uma fronteira reutilizável para a configuração do
MPAS-Atmosphere. O objetivo é evitar que cada aplicação — matriz B,
MONAN-JEDI e experimentos futuros — reimplemente regras de paths, templates,
namelists e streams.

## Responsabilidades

O núcleo `mpas_workflow.case_render` faz somente operações determinísticas:

1. carrega um caso YAML com `includes` relativos e merge recursivo;
2. resolve placeholders explícitos fornecidos pelo caso ou pela linha de
   comando;
3. atualiza grupos/opções de um namelist Fortran;
4. atualiza ou cria streams em XML por nome;
5. escreve os arquivos renderizados e um manifesto JSON com contexto,
   entradas e hashes SHA-256.

Ele não baixa GFS, não chama WPS, não cria matriz B, não depende de JEDI, não
submete PBS e não controla dependências entre tarefas.

## Layout de configuração

Cada caso é um diretório iniciado por `case.yaml`. O arquivo pode compor
configurações reutilizáveis por `includes`, avaliados em ordem e sempre de
forma relativa ao arquivo que os declarou.

```text
configs/mpas/
  defaults/
    mpas-atmosphere.yaml
  sites/
    jaci.yaml
  cases/
    global-x1.10242/
      case.yaml
```

A ordem recomendada é:

```yaml
includes:
  - ../../defaults/mpas-atmosphere.yaml
  - ../../sites/jaci.yaml

case:
  name: global-x1.10242

context:
  mesh_name: x1.10242
  nproc: 128
  graph_basename: x1.10242.graph.info
```

O caso declara os artefatos a renderizar por estágio. A renderização não
interpreta o significado científico das opções; ela apenas aplica a estrutura
fornecida no YAML.

```yaml
stages:
  forecast:
    output_dir: "{work_root}/rendered/{case_name}/f{lead_hours:03d}"
    namelist:
      template: "{atmosphere_share}/namelist.atmosphere"
      output: namelist.atmosphere
      groups:
        nhyd_model:
          config_dt: "{dt}.0"
          config_start_time: "'{init_time}'"
          config_run_duration: "'{run_duration}'"
        damping:
          config_epssm_minimum: "0.1"
          config_epssm_maximum: "0.5"
    streams:
      template: "{atmosphere_share}/streams.atmosphere"
      output: streams.atmosphere
      streams:
        invariant:
          attributes:
            filename_template: "{invariant_local_name}"
```

Uma opção com valor YAML `null` remove a respectiva linha do namelist. Isso
permite que a configuração declare a remoção de opções obsoletas sem criar
exceções codificadas em Python.

## Uso

Em uma instalação Python normal, o comando instalado é `mpas-render`:

```bash
mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage forecast \
  --init-time 2026-06-12_00:00:00 \
  --lead-hours 48 \
  --dt 1200 \
  --set work_root=/p/projetos/monan_das/$USER/work/mpas \
  --set atmosphere_share=/p/projetos/monan_das/$USER/builds/monan-jedi-mpas/share/MPAS/core_atmosphere
```

No JACI, enquanto a instalação editável do pacote não estiver disponível, use
o launcher da árvore do repositório:

```bash
bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage forecast \
  --init-time 2026-06-12_00:00:00 \
  --lead-hours 48 \
  --dt 1200
```

O comando deriva `safe_time`, `valid_time` e `run_duration` a partir de
`init-time` e `lead-hours`. Seu produto é um diretório com os arquivos
renderizados e `mpas-render-manifest.json`.

## Relação com simpleWorkflow

O `simpleWorkflow` continua sendo o orquestrador. Cada etapa MPAS deve ser
exposta como uma tarefa com entradas e saídas explícitas:

```yaml
workflow:
  name: mpas-forecast

context:
  case_dir: configs/mpas/cases/global-x1.10242
  render_dir: /work/rendered/global-x1.10242/f048

tasks:
  - name: render_forecast
    argv:
      - mpas-render
      - --case
      - "{case_dir}"
      - --stage
      - forecast
      - --init-time
      - "{init_time}"
      - --lead-hours
      - "48"
      - --dt
      - "1200"
    outputs:
      required:
        - "{render_dir}/namelist.atmosphere"
        - "{render_dir}/streams.atmosphere"
        - "{render_dir}/mpas-render-manifest.json"
```

Uma tarefa posterior pode preparar links/runtime, e outra pode executar o
modelo via PBS. Assim, renderização, preparação e execução permanecem
idempotentes, observáveis e reutilizáveis entre workflows.

## Migração incremental

Os comandos atuais de init, forecast, NMC e B-matrix permanecem preservados
nesta primeira etapa. A próxima migração deve substituir o uso direto dos
templates de tutorial no `forecast.py` por casos renderizados e contratos de
artefatos. Só depois a camada B-matrix deve consumir o mesmo núcleo MPAS.

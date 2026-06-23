# Faixas de ciclos MPAS

O launcher `scripts/mpaswf-cycle-range` executa uma sequência resumível de:

```text
GFS → ungrib → MPAS init → forecast fNNN → restart + da_state
```

Ele reutiliza o `init`, `restart` e `da_state` que já passaram pela validação
existente. Cada mudança de estado é gravada em um manifesto JSON sob
`<work_root>/cycle-manifests/`; portanto, uma nova execução com os mesmos
argumentos retoma a primeira análise ainda incompleta.

## Execução de uma faixa

Carregue primeiro o ambiente JACI e execute o launcher com `bash`:

```bash
source scripts/load_jaci_env.sh

bash scripts/mpaswf-cycle-range \
  --config configs/jaci-x1.10242.yaml \
  --start 2026-06-01_00:00:00 \
  --end 2026-06-30_00:00:00 \
  --interval-hours 24 \
  --lead-hours 48 \
  --dt 1200 \
  --submit \
  --wait
```

Para uma faixa de quatro ciclos por dia, use `--interval-hours 6`. As datas
de análise precisam possuir os GRIB2 GFS f000 correspondentes, ou a execução
precisa ter acesso à rotina configurada de download.

## Comportamento de submissão

- `--submit --wait` é o modo recomendado: submete o init, espera sua saída do
  PBS, valida o NetCDF produzido, submete o forecast, valida `restart` e
  `da_state`, e só então avança para o próximo horário.
- `--submit` sem `--wait` submete somente o primeiro estágio pendente e encerra
  com o manifesto atualizado. Execute o mesmo comando novamente depois de o
  job terminar para continuar.
- Sem `--submit`, o comando apenas prepara o primeiro estágio pendente para
  inspeção manual.
- `--no-download` impede downloads implícitos e falha de forma explícita quando
  o GFS necessário não está no diretório configurado.
- `--force-forecast` recria um forecast mesmo se as saídas já existirem.

O modo sequencial com `--wait` é proposital: evita que previsões iniciem antes
que o init correspondente tenha sido validado e deixa a retomada segura após
qualquer falha de dados, PBS ou modelo.

## Planejamento sem executar

Use `--dry-run` para gerar ou atualizar somente o manifesto com o estado de
cada horário:

```bash
bash scripts/mpaswf-cycle-range \
  --config configs/jaci-x1.10242.yaml \
  --start 2026-06-01_00:00:00 \
  --end 2026-06-30_00:00:00 \
  --interval-hours 24 \
  --lead-hours 48 \
  --dt 1200 \
  --dry-run
```

## Retomada

Repita exatamente o mesmo comando. O manifesto é identificado pelo intervalo,
lead time e `dt`; os ciclos cujo `restart` e `da_state` já existem são marcados
como concluídos e ignorados. Para usar outro arquivo de controle, informe
`--manifest /caminho/arquivo.json`.

## Execução de longa duração no JACI

Uma execução mensal com `--wait` deve ser iniciada em uma sessão persistente,
por exemplo `tmux` ou `screen`, porque o processo controlador permanece ativo
para monitorar e validar os jobs PBS. O trabalho científico pesado continua
sendo executado nos jobs PBS; o controlador apenas coordena as dependências e
escreve o manifesto.

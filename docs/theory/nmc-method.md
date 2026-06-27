# Método NMC

## Objetivo

O método NMC é uma forma clássica de estimar estatísticas de erro de background usando diferenças entre previsões de diferentes alcances válidas no mesmo horário.

Neste workflow, a perturbação básica é:

```text
δx = forecast_48h - forecast_24h
```

## Ideia central

Se duas previsões têm o mesmo tempo válido, mas foram iniciadas em horários diferentes, a diferença entre elas contém informação sobre o crescimento do erro de previsão.

```text
Inicialização t-48h ─── forecast 48h ───┐
                                        ├── mesmo tempo válido t → diferença
Inicialização t-24h ─── forecast 24h ───┘
```

A diferença é usada como proxy estatístico do erro de background.

## Por que f48 - f24?

A escolha f48 - f24 é comum porque:

- ambas são previsões curtas o suficiente para manter estrutura sinótica realista;
- f48 contém mais crescimento de erro que f24;
- a diferença tende a capturar estruturas típicas de erro de previsão;
- é possível acumular muitas amostras a partir de ciclos operacionais.

## Hipóteses

O método assume que:

- diferenças entre previsões representam uma amostra razoável do erro de background;
- as estatísticas médias dessas diferenças são representativas do sistema;
- o modelo, a resolução e as fontes de dados são consistentes com o sistema de assimilação alvo.

## Limitações

O método NMC não mede diretamente o erro de background. Ele usa uma aproximação. Algumas limitações:

- pode superestimar ou subestimar erros reais;
- depende do modelo e da configuração de previsão;
- pode refletir erro de modelo e não apenas erro inicial;
- pode depender da estação do ano;
- requer número suficiente de amostras;
- não captura covariâncias dependentes do fluxo em tempo real.

## Número de amostras

Quanto mais amostras, melhor a estimativa estatística. Uma matriz B baseada em poucas amostras pode apresentar:

- variâncias ruidosas;
- correlações espúrias;
- balanços instáveis;
- sensibilidade forte a casos individuais.

Para smoke tests, poucas amostras podem ser suficientes para validar o software. Para uma matriz científica ou operacional, é necessário um conjunto maior e bem distribuído.

## Sazonalidade

A matriz B pode variar sazonalmente. Uma B anual média pode ser robusta, mas menos representativa para estações específicas. Uma B sazonal pode representar melhor regimes de erro, mas exige mais amostras por estação.

## Aplicação neste workflow

Neste repositório:

1. `mpasforecast` gera previsões f24/f48.
2. `mpasbflow` calcula `forecast_48h - forecast_24h`.
3. As perturbações são convertidas para variáveis de controle.
4. SABER/BUMP estima estatísticas a partir dessas amostras.

## Produtos relacionados

- `FULL_f48.nc`
- `FULL_f24.nc`
- `PTB_f48mf24.nc`
- `manifest.tsv`

## Validação

As diferenças NMC devem ser verificadas com:

```bash
mpasverify compare --old baseline/PTB_f48mf24.nc --new novo/PTB_f48mf24.nc
```

Além disso, é recomendado inspecionar estatísticas globais por variável e verificar se as diferenças possuem magnitude física plausível.

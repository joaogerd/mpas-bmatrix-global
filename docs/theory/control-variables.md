# Variáveis de controle

## Objetivo

As variáveis de controle são as variáveis nas quais a matriz B é representada e aplicada. A escolha dessas variáveis influencia diretamente o equilíbrio físico, a estrutura espacial e a estabilidade numérica dos incrementos.

Neste workflow, as variáveis de controle principais são:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

## Por que não usar diretamente `u` e `v`?

Os componentes horizontais de vento `u` e `v` misturam contribuições rotacionais e divergentes. Para assimilação variacional, é frequentemente mais útil separar o vento em:

- componente rotacional;
- componente divergente.

Essa separação é feita por meio de:

```text
stream_function       → função de corrente, associada à parte rotacional
velocity_potential    → potencial de velocidade, associado à parte divergente
```

## Conversão `u/v -> psi/chi`

A conversão é feita em uma grade regular lat/lon usando harmônicos esféricos:

```text
u, v → ψ, χ
```

No projeto, essa etapa é implementada em Python com `windspharm`, substituindo a antiga função NCL `uv2sfvp*`.

## Temperatura

O MPAS pode armazenar variáveis termodinâmicas em formas nativas, como `theta`. Para a matriz B, o workflow utiliza `temperature`, mais diretamente interpretável na etapa SABER/JEDI.

## Umidade específica

A variável nativa `qv` é convertida para `spechum`:

```text
spechum = qv / (1 + qv)
```

Isso evita inconsistências entre razão de mistura e umidade específica.

## Pressão de superfície

`surface_pressure` representa a componente de massa em superfície. Ela é importante para o balanceamento multivariado e para resposta de larga escala.

## Relação com variáveis de análise

As variáveis de controle podem ser diferentes das variáveis de análise. O SABER/JEDI usa transformações lineares para converter incrementos entre espaços.

Exemplo conceitual:

```text
controle: stream_function, velocity_potential, temperature, spechum, surface_pressure
                       ↓
                  Control2Analysis
                       ↓
análise: uReconstructZonal, uReconstructMeridional, temperature, spechum, surface_pressure
```

## Relação com VBAL

O balanceamento vertical usa `stream_function` como variável explicativa para componentes balanceadas de:

- `velocity_potential`;
- `temperature`;
- `surface_pressure`.

## Relação com NICAS

O NICAS é treinado por variável de controle. Cada variável possui sua própria representação de correlação/localização, depois mesclada em produtos globais.

## Boas práticas

- Manter nomes de variáveis consistentes entre BFLOW, VBAL, HDIAG, NICAS e SO.
- Validar arquivos intermediários após conversões.
- Comparar `stream_function` e `velocity_potential` com baseline ao trocar backend ou pesos.
- Evitar misturar nomes físicos, nomes nativos do MPAS e nomes JEDI sem documentação explícita.

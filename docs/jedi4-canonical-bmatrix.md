# Matriz B canônica para JEDI 4

Este documento registra a migração da matriz B global MPAS para a convenção usada pelo MPAS-JEDI 4.

## Objetivo

A matriz B nova deve deixar de depender de `alias` no YAML do JEDI. Para isso, os arquivos `FULL` e `PTB` gerados pelo BFLOW devem conter diretamente os nomes canônicos usados pelo MPAS-JEDI/SABER.

## Variáveis de controle canônicas

O contrato `configs/bmatrix-x1.10242-jedi4.yaml` usa:

```text
air_horizontal_streamfunction
air_horizontal_velocity_potential
air_temperature
water_vapor_mixing_ratio_wrt_moist_air
air_pressure_at_surface
```

Os nomes físicos antigos não devem aparecer como variáveis de controle em PTBs novos:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

## Validação local

Antes de rodar no JACI, valide o contrato:

```bash
python scripts/validate_jedi4_contract.py configs/bmatrix-x1.10242-jedi4.yaml
```

## Validação no JACI

A sequência mínima é:

```bash
mpasbflow all --config configs/jaci-x1.10242.yaml
mpasbcov vbal-prepare --config configs/jaci-x1.10242.yaml
```

Durante esta branch, a configuração de plataforma ainda aponta para o contrato padrão. Para testar o contrato JEDI-4 sem alterar o arquivo público, use uma cópia local de `configs/jaci-x1.10242.yaml` com:

```yaml
bmatrix:
  configuration: bmatrix-x1.10242-jedi4.yaml
```

Depois do VBAL, confirmar explicitamente se os produtos gerados contêm a componente `unbalanced`. Não alterar a direção de `balanced_variable`/`unbalanced_variable` antes dessa inspeção.

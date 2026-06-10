# mpas-bmatrix-global

Workflow reprodutível para gerar uma matriz B estática global para MPAS-JEDI/MONAN-JEDI.

## Objetivo

Este repositório organiza o fluxo para:

1. gerar condições iniciais globais para o MPAS;
2. rodar previsões MPAS globais de 24 h e 48 h;
3. formar perturbações NMC do tipo `f48 - f24`;
4. usar o `mpasjedi_error_covariance_toolbox.x` para gerar estatísticas de erro;
5. produzir uma matriz B estática univariada para uso no MPAS-JEDI.

## Estratégia inicial

A primeira versão do fluxo usa uma B univariada global, sem `BUMP_VerticalBalance`.

Variáveis alvo:

- `eastward_wind`
- `northward_wind`
- `air_temperature`
- `water_vapor_mixing_ratio_wrt_moist_air`
- `air_pressure_at_surface`

A versão multivariada com `air_horizontal_streamfunction`,
`air_horizontal_velocity_potential` e `BUMP_VerticalBalance` será tratada
apenas depois que a B univariada estiver validada.

## Executáveis MPAS no JACI

Neste build, os executáveis do MPAS aparecem com nomes prefixados:

- `mpas_init_atmosphere`
- `mpas_atmosphere`
- `mpas_atmosphere_build_tables`

Caminho atual:

```text
/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/bin
````

## Malha piloto

A malha inicial para desenvolvimento é:

```text
x1.10242_240km
```

Arquivos:

```text
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/mesh/x1.10242.grid.nc
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info
```

## Precisão do MPAS

Este workflow foi iniciado usando o `mpas-bundle` com:

```text
-DMPAS_DOUBLE_PRECISION=OFF

## Fluxo planejado

```text
dados globais externos
  -> mpas_init_atmosphere
  -> init.nc
  -> mpas_atmosphere
  -> f024.nc / f048.nc
  -> perturbações NMC
  -> StdDev
  -> NICAS
  -> B estática
```

## Estado atual

* Domínio: global.
* LBC regional: não será usado.
* MPAS: disponível no build `monan-jedi-mpas`.
* Condições iniciais: ainda precisam ser geradas.
* Fonte inicial de dados meteorológicos: ainda será definida.

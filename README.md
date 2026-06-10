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

## Etapas

```text
dados globais externos
  -> init_atmosphere_model
  -> init.nc
  -> atmosphere_model
  -> f024.nc / f048.nc
  -> perturbações NMC
  -> StdDev
  -> NICAS
  -> B estática

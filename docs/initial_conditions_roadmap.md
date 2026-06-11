# Roteiro para gerar condições iniciais globais MPAS

## Estado após inventário

O inventário `scripts/legacy/09_inventory_initial_condition_sources.sh` mostrou que o ambiente JACI atual já possui:

- `mpas_init_atmosphere`;
- `mpas_atmosphere`;
- `mpas_atmosphere_build_tables`;
- `ncdump`;
- `gpmetis`;
- malhas globais MPAS, incluindo `x1.10242`;
- arquivos `x1.10242.invariant.nc` usados nos testes MPAS-JEDI.

Também mostrou que ainda faltam, no espaço inventariado:

- `ungrib.exe`;
- `link_grib.csh`;
- Vtables reais do WPS;
- diretório WPS geog real;
- GRIBs globais úteis;
- arquivos intermediários WPS `FILE:*`.

Portanto, a geração de `init.nc` independente ainda depende de obter ou produzir arquivos intermediários WPS e apontar `config_geog_data_path` para um diretório geográfico válido.

## Caminho recomendado

Para a primeira versão reprodutível, usar análise global GFS/GDAS ou equivalente e gerar arquivos intermediários WPS `FILE:*` com `ungrib.exe`.

Fluxo esperado:

```text
GRIB global
  -> link_grib.csh
  -> ungrib.exe + Vtable
  -> FILE:YYYY-MM-DD_HH
  -> mpas_init_atmosphere
  -> x1.10242.init.YYYY-MM-DD_HH.00.00.nc
```

## Configuração MPAS init

O `namelist.init_atmosphere` instalado vem com valores de exemplo para `x1.40962`. Para o piloto `x1.10242`, os pontos mínimos a substituir são:

```text
config_start_time
config_stop_time
config_geog_data_path
config_met_prefix
config_fg_interval
config_block_decomp_file_prefix
```

O `streams.init_atmosphere` instalado também vem apontando para `x1.40962.grid.nc` e `x1.40962.init.nc`. Para o piloto, deve apontar para:

```text
input:  x1.10242.grid.nc
output: x1.10242.init.YYYY-MM-DD_HH.00.00.nc
```

## Observação sobre `invariant.nc`

O arquivo `x1.10242.invariant.nc` já permitiu rodar o MPAS por 48 h a partir de um estado existente do tutorial. Porém, ele não substitui a necessidade de gerar condições iniciais independentes para formar pares NMC reais.

Para NMC real, é necessário ter forecasts independentes:

```text
validade T:
  f48 iniciado em T-48h
  f24 iniciado em T-24h
```

## Próximas etapas práticas

1. Obter ou compilar WPS/ungrib no JACI.
2. Definir uma Vtable para a fonte escolhida, preferencialmente GFS/GDAS no primeiro teste.
3. Definir o diretório WPS geog.
4. Gerar `FILE:*` para um ciclo piloto.
5. Rodar `scripts/legacy/10_prepare_init_from_wps_intermediate.sh`.
6. Submeter `mpas_init_atmosphere` para gerar o primeiro `init.nc` independente.

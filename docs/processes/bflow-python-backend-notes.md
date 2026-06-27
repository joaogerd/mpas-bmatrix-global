# BFLOW Python backend notes

Esta nota documenta a remoção do NCL nas etapas de aplicação de pesos e conversão `u/v -> psi/chi`.

## Ordem preservada do fluxo antigo

O fluxo NCL original fazia:

```text
MPAS u/v
  -> ESMF_regrid_with_weights: MPAS -> lat/lon 1 grau
  -> uv2sfvpf: u/v -> stream_function/velocity_potential
  -> ESMF_regrid_with_weights: lat/lon 1 grau -> MPAS
  -> FULL_f48.nc / FULL_f24.nc
```

O fluxo Python mantém a mesma ordem:

```text
MPAS u/v
  -> aplicação Python dos pesos ESMF row/col/S: MPAS -> lat/lon 1 grau
  -> windspharm VectorWind.sfvp()
  -> aplicação Python dos pesos ESMF row/col/S: lat/lon 1 grau -> MPAS
  -> FULL_f48.nc / FULL_f24.nc
```

## Pesos ESMF

`bflow_core/weights.py` não gera mais script NCL. Ele espera encontrar os arquivos de peso ESMF já validados no workspace:

```text
ESMF_weights/MPAS_<mesh>_to_latlon_1p0_bilinear.nc
ESMF_weights/latlon_1p0_to_MPAS_<mesh>_bilinear.nc
```

Esses arquivos podem ser:

- reutilizados do fluxo antigo baseado em ESMF/NCL;
- gerados uma vez por ESMF/xESMF em etapa separada;
- copiados para o workspace BFLOW antes de rodar `mpasbflow run --skip-weights` ou `mpasbflow all --skip-weights`.

A aplicação dos pesos é feita diretamente em Python lendo as variáveis ESMF:

```text
row, col, S
```

Assim evitamos uma interpolação aproximada e usamos a mesma matriz esparsa dos pesos ESMF.

## Conversão `u/v -> psi/chi`

`bflow_core/psichi.py` não chama mais `uv2sfvpf` do NCL. A conversão é feita com:

```python
from windspharm.standard import VectorWind
psi, chi = VectorWind(u, v, gridtype="regular").sfvp()
```

O código ajusta a ordem das dimensões para o formato esperado pelo `windspharm`:

```text
BFLOW interno:       (nlev, nlat, nlon)
windspharm.standard: (nlat, nlon, nlev)
```

Também inverte a latitude antes/depois da chamada porque `windspharm` espera latitude de norte para sul.

## Dependências

O backend Python requer:

```text
netCDF4
numpy
windspharm
```

Recomendação de instalação no ambiente JACI/Conda:

```bash
conda install -c conda-forge windspharm pyspharm
```

## Validação necessária

Apesar de esta versão ser conceitualmente mais próxima do NCL do que a aproximação anterior por FFT/IDW, ainda é necessário validar contra um baseline antigo porque podem existir diferenças em:

- ordem de achatamento da grade ESMF;
- convenção de latitude/longitude;
- sinal de `velocity_potential`;
- precisão numérica entre `uv2sfvpf` e `windspharm`;
- atributos e dimensões do NetCDF final.

Comparar pelo menos:

- `stream_function`;
- `velocity_potential`;
- `PTB_f48mf24.nc` final;
- impacto posterior em `VBAL`, `HDIAG`, `NICAS` e `SO`.

## Teste recomendado

Rodar o mesmo período curto usado no smoke BFLOW com o backend antigo e novo e comparar:

```bash
ncdiff old/PTB_f48mf24.nc new/PTB_f48mf24.nc diff.nc
ncks -H -C -v stream_function diff.nc | head
ncks -H -C -v velocity_potential diff.nc | head
```

Também é recomendável calcular estatísticas globais por variável:

- média;
- desvio padrão;
- RMSE;
- correlação espacial por nível vertical.

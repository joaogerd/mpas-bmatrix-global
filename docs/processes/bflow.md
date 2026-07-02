# BFLOW

BFLOW prepara as amostras NMC `PTB_f48mf24.nc` usadas na calibração da matriz B do MPAS-JEDI/SABER.

```text
PTB = forecast(f48) - forecast(f24)
```

Os dois forecasts têm o mesmo horário válido. BFLOW não executa a assimilação: ele produz as perturbações consumidas por VBAL, HDIAG e NICAS.

## Pipeline Python

O comando `mpasbflow` executa um pipeline Python sem NCL, scripts auxiliares persistentes ou um script mestre shell:

1. prepara o workspace e liga os pares `f048`/`f024`;
2. reutiliza pesos ESMF válidos ou os gera quando faltam;
3. cria `template_PTB.nc`;
4. transforma `u/v` em função de corrente e potencial de velocidade;
5. copia e deriva variáveis físicas;
6. calcula a diferença NMC;
7. valida os produtos finais.

Os pesos são gerados por `xESMF`, que usa ESMPy/ESMF através de Python. `UXarray` lê a topologia MPAS e a normaliza para UGRID no sentido MPAS → lat-lon. O sentido lat-lon → MPAS interpola a grade auxiliar nos centros `nCells`, que são os pontos onde BFLOW grava `stream_function` e `velocity_potential`.

## Pesos ESMF

A resolução, o método, os limites, os nomes e o diretório são definidos em `bflow.regridding` no contrato científico da matriz B.

```yaml
bflow:
  regridding:
    weights_directory: ESMF_weights
    mesh_file: /caminho/opcional/para/mesh.nc  # por padrão usa mesh.grid
    scrip_resolution: 1.0deg                   # também aceita 0.5x0.5
    interpolation_method: bilinear
    periodic: true
    lower_left: [-89.5, -179.5]
    upper_right: [89.5, 179.5]
    weight_latlon_to_mpas: latlon_1p0_to_MPAS_{mesh_name}_bilinear.nc
    weight_mpas_to_latlon: MPAS_{mesh_name}_to_latlon_1p0_bilinear.nc
```

`{mesh_name}` é resolvido a partir de `mesh.name`. Um diretório relativo é criado dentro do workspace BFLOW. Não há nomes de pesos, resolução de 1 grau, método ou caminhos fixos no código.

Na primeira execução, se um dos arquivos não existir, BFLOW gera somente o arquivo ausente. Se ambos existirem, valida `row`, `col` e `S` e os reutiliza. `--skip-weights` impede a geração automática e exige que ambos já existam e sejam válidos.

Métodos suportados são `bilinear`, `patch`, `nearest_s2d` e `nearest_d2s`. Métodos conservativos não se aplicam ao sentido lat-lon → centros MPAS, pois esse sentido usa um LocStream de pontos e não polígonos de destino.

## Dependências

O ambiente Conda `mpaswf` precisa incluir:

```text
netcdf4
numpy
xarray
windspharm
pyspharm
esmpy
xesmf
uxarray
```

A criação do ambiente a partir de `environment.yml` instala as dependências compiladas via conda-forge:

```bash
conda env create -f environment.yml
conda activate mpaswf
python -m pip install -e .
```

## Uso

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --clean-output \
  --force
```

Use `prepare` para somente montar o workspace e `run` para executar um workspace já preparado:

```bash
mpasbflow prepare --config configs/jaci-x1.10242.yaml ...
mpasbflow run --config configs/jaci-x1.10242.yaml --workspace /caminho/do/workspace
```

Os principais produtos são:

```text
manifest.tsv
ESMF_weights/*.nc
output/YYYYMMDDHH/FULL_f48.nc
output/YYYYMMDDHH/FULL_f24.nc
output/YYYYMMDDHH/PTB_f48mf24.nc
```

## Reprodutibilidade

Os pesos dependem da geometria MPAS, da grade lat-lon auxiliar, dos limites e do método de interpolação. Modifique qualquer um desses parâmetros apenas em um workspace novo; em seguida refaça BFLOW e todas as etapas posteriores da matriz B.

# Instalação e validação do WPS/ungrib no JACI

## Finalidade

O `ungrib.exe` do WPS converte dados GFS em GRIB para arquivos intermediários usados na preparação das condições iniciais do MPAS. Ele é um pré-requisito somente quando as amostras NMC serão produzidas a partir de previsões MPAS inicializadas com GFS/GRIB.

A implementação está em [`scripts/wps`](../scripts/wps/README.md), não contém caminhos fixos de conta e pode ser reexecutada com segurança.

## Instalação

Na raiz do repositório:

```bash
source scripts/load_jaci_env.sh

bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/2_probe_wps_build_environment.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

O passo 2 é somente diagnóstico. O passo 3 aplica automaticamente o patch JasPer em `ungrib/src/ngl/g2/dec_jpeg2000.c`, trocando `jpc_decode()` pela API pública `jas_image_decode(..., jas_image_strtofmt("jpc"), ...)`, antes de configurar ou compilar. Não existe uma etapa de patch separada para o usuário executar.

## Caminhos e configuração

Os scripts determinam a raiz do repositório automaticamente. O diretório padrão de dados é `<repositorio>/data` para um clone comum ou `<workspace>/data/mpas-bmatrix-global` quando o checkout está em `<workspace>/projects/mpas-bmatrix-global`.

No layout usual do JACI, o WPS será instalado em:

```text
/p/projetos/monan_das/$USER/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Para outra localização:

```bash
export DATA_ROOT=/caminho/para/dados/mpas-bmatrix-global
bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

Ao final, use o `WPS_SRC_DIR` mostrado pelo script na configuração do workflow:

```yaml
wps:
  root: /caminho/mostrado/em/WPS_SRC_DIR
  ungrib_exe: /caminho/mostrado/em/WPS_SRC_DIR/ungrib.exe
  link_grib: /caminho/mostrado/em/WPS_SRC_DIR/link_grib.csh
  vtable_gfs: /caminho/mostrado/em/WPS_SRC_DIR/ungrib/Variable_Tables/Vtable.GFS
```

## Dependências GRIB2

O build detecta NetCDF, JasPer, libpng e zlib no ambiente carregado e a partir de `nc-config` e `nf-config`. Para uma instalação Spack fora das raízes detectadas:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/spack/install
bash scripts/wps/2_probe_wps_build_environment.sh
```

Também é possível fornecer explicitamente `JASPERINC`, `JASPERLIB`, `PNG_INC`, `PNG_LIB`, `ZLIB_INC` e `ZLIB_LIB`.

## Verificação

```bash
ls -lh "$WPS_SRC_DIR/ungrib.exe"
file "$WPS_SRC_DIR/ungrib.exe"
ldd "$WPS_SRC_DIR/ungrib.exe" | grep -Ei 'not found|netcdf|jasper|png|zlib|hdf5|curl' || true
```

É normal que `ungrib.exe` reclame de `namelist.wps` quando iniciado fora de um diretório de execução preparado. O essencial é que o executável exista, seja executável e não apresente bibliotecas obrigatórias ausentes.

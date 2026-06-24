# Instalação e validação do WPS/ungrib no JACI

## Finalidade

O `ungrib.exe` do WPS converte dados GFS em GRIB para arquivos intermediários usados na preparação das condições iniciais do MPAS. Ele é um pré-requisito **somente** quando as amostras NMC serão produzidas a partir de previsões MPAS inicializadas com GFS/GRIB.

A implementação atual está em [`scripts/wps`](../scripts/wps/README.md). Ela substitui os scripts históricos em `scripts/legacy`, não contém caminhos fixos de uma conta de usuário e pode ser reexecutada com segurança.

## Instalação

A partir da raiz do repositório:

```bash
source scripts/load_jaci_env.sh

bash scripts/wps/10_download_wps_assets.sh
bash scripts/wps/11_probe_wps_build_environment.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

O passo 11 é não destrutivo: ele apenas verifica as dependências. Antes de decidir se pode reaproveitar `ungrib.exe`, o passo 12 aplica automaticamente o patch JasPer em `ungrib/src/ngl/g2/dec_jpeg2000.c`: a chamada obsoleta `jpc_decode()` é substituída pela API pública `jas_image_decode(..., jas_image_strtofmt("jpc"), ...)`.

O script `scripts/wps/14_patch_wps_dec_jpeg2000.sh` permanece disponível para inspeção ou aplicação isolada do patch, mas **não é uma etapa manual do procedimento normal**, pois já é chamado pelo passo 12. Quando a fonte é corrigida após a criação de um executável, o build detecta que ela está mais nova e recompila, evitando a reutilização de um `ungrib.exe` desatualizado.

## Caminhos e configuração

Os scripts determinam a raiz do repositório automaticamente. O diretório padrão de dados é:

- `<repositorio>/data`, para um clone em local arbitrário; ou
- `<workspace>/data/mpas-bmatrix-global`, quando o repositório está em `<workspace>/projects/mpas-bmatrix-global`.

No layout usual do JACI, isso preserva a convenção:

```text
/p/projetos/monan_das/$USER/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Para usar outra localização, exporte `DATA_ROOT` antes de executar os scripts:

```bash
export DATA_ROOT=/caminho/para/dados/mpas-bmatrix-global
bash scripts/wps/10_download_wps_assets.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

Ao final, o script mostra `WPS_SRC_DIR`. Use esse valor em sua configuração de workflow:

```yaml
wps:
  root: /caminho/mostrado/em/WPS_SRC_DIR
  ungrib_exe: /caminho/mostrado/em/WPS_SRC_DIR/ungrib.exe
  link_grib: /caminho/mostrado/em/WPS_SRC_DIR/link_grib.csh
  vtable_gfs: /caminho/mostrado/em/WPS_SRC_DIR/ungrib/Variable_Tables/Vtable.GFS
```

## Dependências GRIB2

O build detecta NetCDF, JasPer, libpng e zlib a partir do ambiente carregado e dos prefixos retornados por `nc-config` e `nf-config`. Para uma instalação Spack fora das raízes detectadas, informe:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/spack/install
bash scripts/wps/11_probe_wps_build_environment.sh
```

Também é possível fornecer explicitamente `JASPERINC`, `JASPERLIB`, `PNG_INC`, `PNG_LIB`, `ZLIB_INC` e `ZLIB_LIB`. Consulte [`scripts/wps/README.md`](../scripts/wps/README.md) para todas as variáveis e os controles de reexecução.

## Verificação

```bash
ls -lh "$WPS_SRC_DIR/ungrib.exe"
file "$WPS_SRC_DIR/ungrib.exe"
ldd "$WPS_SRC_DIR/ungrib.exe" | grep -Ei 'not found|netcdf|jasper|png|zlib|hdf5|curl' || true
```

É normal que `ungrib.exe` reclame de `namelist.wps` quando iniciado fora de um diretório de execução preparado. O ponto principal é que o executável exista, seja executável e não apresente bibliotecas obrigatórias ausentes.

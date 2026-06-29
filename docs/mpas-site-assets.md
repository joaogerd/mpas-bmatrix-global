# Ativos de site MPAS: MONAN 1.4.x / MPAS 8.3.1

## Objetivo

O estágio `static` do MPAS precisa de dados geográficos permanentes: relevo,
uso da terra, solo, vegetação, albedo, neve e SoilGrids. Eles não pertencem a
um ciclo GFS nem devem ser baixados ou copiados para cada experimento.

No JACI, o caso global usa a árvore institucional do MONAN 1.4.x, baseada em
MPAS 8.3.1, como fonte primária somente leitura:

```text
/p/projetos/monan_adm/monan/dados/MONAN_v1.4.x/MONAN_datain/datain/WPS_GEOG
```

A árvore compartilhada não contém `soiltype_bot_30s`. O perfil declara o
repositório local do usuário como overlay para esse e futuros complementos:

```text
<pasta de dados do projeto>/external/WPS_GEOG/low_res_mandatory/WPS_GEOG_LOW_RES
```

## Visão de geografia

`mpas-assets prepare` cria uma visão em:

```text
<pasta de dados do projeto>/assets/WPS_GEOG/monan-1.4-mpas-8.3.1
```

Essa visão contém apenas links simbólicos. Nenhum geotile da árvore MONAN é
copiado ou modificado. A fonte compartilhada tem precedência; o overlay apenas
fornece diretórios de primeiro nível que não existem nela.

O manifesto `mpas-wps-geog-assets.json` registra a origem de cada índice
obrigatório, tamanho e instante de modificação. Ele deve ser preservado junto
com os manifestos de runtime para reprodutibilidade.

## Uso

Validar fontes sem criar links:

```bash
mpas-assets validate --case configs/mpas/cases/global-x1.10242.yaml
```

Validar e criar a visão de links:

```bash
mpas-assets prepare --case configs/mpas/cases/global-x1.10242.yaml
```

`mpas-cycle static` chama a mesma preparação automaticamente antes do PBS.
Assim, recomenda-se executar `mpas-assets validate` durante instalação ou CI e
usar o comando `prepare` somente quando a árvore de ativos mudar.

## Contrato atual do static

O perfil JACI exige índices para GMTED2010, MODIS land use, tipos de solo
STATSGO, temperatura do solo, albedo, vegetação, LAI e SoilGrids. O contrato é
declarado em `configs/sites/jaci.yaml` e repetido no contrato de runtime para
que `mpas-stage-prepare` também falhe cedo.

A instalação usada para assimilação continua sendo `monan-jedi-mpas`. A
referência MONAN 1.4.x/MPAS 8.3.1 nesta camada identifica os dados fixos e os
contratos de entrada, não substitui os executáveis JEDI sem uma validação de
compatibilidade explícita.

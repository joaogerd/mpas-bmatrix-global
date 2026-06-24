# Documentação: matriz B global MPAS-JEDI no JACI

Este conjunto de documentos separa a preparação do ambiente dos procedimentos de geração e validação da matriz B estática global usada pelo MPAS-JEDI/SABER.

## Ordem recomendada de leitura

1. [Instalação do ambiente Python `mpaswf`](install-mpaswf-jaci.md)
2. [Instalação e validação do WPS/ungrib](install-wps-ungrib-jaci.md), quando as amostras NMC forem geradas a partir de dados GFS/GRIB
3. [Tutorial de geração da matriz B global](generate-global-bmatrix-jaci.md)

## Escopo de cada documento

| Documento | Conteúdo |
| --- | --- |
| `install-mpaswf-jaci.md` | Criação do ambiente Conda, dependências Python, instalação editável e verificação dos comandos do workflow. |
| `install-wps-ungrib-jaci.md` | Preparação, compilação e validação do `ungrib.exe` no JACI. |
| `generate-global-bmatrix-jaci.md` | Pré-requisitos, arquivos estáticos, geração das amostras NMC, BFLOW, VBAL, HDIAG, NICAS, SO, DIRAC e produtos finais da B. |

> O WPS/ungrib é necessário apenas quando a geração das amostras NMC depende de dados de entrada em formato GFS/GRIB.

# Documentação: matriz B global MPAS-JEDI no JACI

Este conjunto de documentos separa a preparação do ambiente dos procedimentos de geração e validação da matriz B estática global usada pelo MPAS-JEDI/SABER. Cada guia de instalação é idempotente e autônomo: ele inclui os passos necessários para instalar ou reutilizar o próprio componente, sem exigir a execução prévia de outro guia de instalação.

## Ordem recomendada de leitura

1. [Instalação do ambiente Python `mpaswf`](install-mpaswf-jaci.md)
2. [Instalação e validação do WPS/ungrib](install-wps-ungrib-jaci.md), quando as amostras NMC forem geradas a partir de dados GFS/GRIB
3. [Tutorial de geração da matriz B global](generate-global-bmatrix-jaci.md)

## Escopo de cada documento

| Documento | Conteúdo |
| --- | --- |
| `install-mpaswf-jaci.md` | Guia autônomo e idempotente para criação ou reutilização do ambiente Conda, dependências Python, instalação editável e verificação dos comandos do workflow. |
| `install-wps-ungrib-jaci.md` | Guia autônomo e idempotente para preparação, compilação e validação do `ungrib.exe` no JACI, sem depender do ambiente `mpaswf`. |
| `generate-global-bmatrix-jaci.md` | Pré-requisitos, arquivos estáticos, geração das amostras NMC, BFLOW, VBAL, HDIAG, NICAS, SO, DIRAC e produtos finais da B. |

> O WPS/ungrib é necessário apenas quando a geração das amostras NMC depende de dados de entrada em formato GFS/GRIB.

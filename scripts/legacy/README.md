# Scripts legados

Este diretório contém os scripts shell usados durante a construção e validação inicial do workflow MPAS.

Eles foram mantidos como referência histórica e para rastreabilidade, mas o fluxo recomendado agora é usar a CLI Python:

```bash
mpaswf --help
````

ou, sem instalação:

```bash
scripts/mpaswf --help
```

Os scripts legados não devem ser usados como interface principal do sistema. Novas funcionalidades devem ser implementadas em `src/mpas_workflow/`.


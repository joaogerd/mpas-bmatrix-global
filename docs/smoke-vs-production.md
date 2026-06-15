# Smoke test e configuração de produção

O caso `configs/jaci-x1.10242.yaml` representa o caminho smoke test validado no JACI.

Ele deve continuar pequeno, reproduzível e barato o suficiente para depuração:

- malha `x1.10242`;
- 128 ranks;
- 4 membros no ciclo validado;
- cadeia validada até SO e Dirac.

## Regra de manutenção

Não aumentar o custo do smoke test para objetivos de produção. Mudanças de produção devem entrar em configuração própria ou em documentação separada.

## Produção

Uma configuração de produção deve definir explicitamente:

- número de membros maior que o smoke test;
- período de amostragem mais longo;
- filas e walltime adequados;
- localização dos produtos finais;
- política de retenção de logs e arquivos intermediários.

## Estado atual

A separação ainda é documental. O próximo passo é criar uma configuração de produção real quando os parâmetros de membros, período e filas estiverem definidos.

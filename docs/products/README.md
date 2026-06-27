# Produtos do workflow

Esta seção documenta os principais arquivos gerados pelo workflow de matriz B.

A organização por produto complementa a documentação por ferramenta. No uso diário, muitas dúvidas surgem a partir de arquivos específicos, por exemplo:

- O que é `PTB_f48mf24.nc`?
- Quem gera `mpas.stddev.nc`?
- Quem usa `mpas_nicas.nc`?
- Como validar `mpas_vbal_local_*.nc`?

## Produtos documentados

| Produto | Documento | Produzido por | Usado por |
| --- | --- | --- | --- |
| `FULL_f24.nc` / `FULL_f48.nc` | [full-forecast.md](full-forecast.md) | `mpasbflow` | `mpasbflow`, `mpasvbal` |
| `PTB_f48mf24.nc` | [ptb.md](ptb.md) | `mpasbflow` | `mpasvbal`, `mpashdiag`, `mpasnicas` |
| `mpas_vbal.nc` | [mpas-vbal.md](mpas-vbal.md) | `mpasvbal` | `mpashdiag`, `mpasso` |
| `mpas.stddev.nc` | [mpas-stddev.md](mpas-stddev.md) | `mpashdiag` | `mpasso`, SABER |
| `mpas.cor_rh.nc` / `mpas.cor_rv.nc` | [mpas-correlations.md](mpas-correlations.md) | `mpashdiag` | `mpasnicas` |
| `mpas_nicas.nc` | [mpas-nicas.md](mpas-nicas.md) | `mpasnicas` | `mpasso`, SABER |
| `an.*.nc` / `obsout_SO_*.h5` | [single-observation-products.md](single-observation-products.md) | `mpasso` | validação |

## Como usar esta seção

Use esta documentação quando você já tem um arquivo em mãos e quer entender:

- sua origem;
- seu conteúdo;
- sua função no pipeline;
- como validá-lo;
- quais etapas dependem dele.

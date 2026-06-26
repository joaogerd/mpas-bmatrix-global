# Próxima etapa: remover NCL do BFLOW

A refatoração atual removeu o `run_all_bflow.sh` como orquestrador principal e transformou as etapas Python geradas em módulos reais. O BFLOW ainda não é completamente Python puro porque duas partes continuam usando NCL como backend externo.

## Partes ainda externas

| Módulo | Função | Dependência atual | Motivo |
|---|---|---|---|
| `bflow_core/weights.py` | `generate_esmf_weights()` | NCL + ESMF regridding scripts | Gera pesos entre grade lat/lon 1 grau e malha MPAS. |
| `bflow_core/psichi.py` | `convert_uv_to_psichi()` | NCL `uv2sfvpf` + pesos ESMF | Converte `uReconstructZonal`/`uReconstructMeridional` para `stream_function`/`velocity_potential`. |

## Caminho recomendado

1. **Isolar contrato numérico**
   - entrada: `uReconstructZonal`, `uReconstructMeridional`, `theta`, pesos ou grade;
   - saída: `FULL_f48.nc`/`FULL_f24.nc` com `stream_function` e `velocity_potential`;
   - tolerância aceitável contra o resultado NCL atual.

2. **Criar testes de regressão**
   - usar uma amostra pequena da malha `x1.10242`;
   - comparar `stream_function` e `velocity_potential` gerados pelo NCL atual contra a nova implementação Python;
   - medir diferenças absolutas, relativas e estatísticas globais.

3. **Substituir geração de pesos**
   - avaliar `ESMF/esmpy`, `xesmf` ou uma implementação própria para MPAS;
   - evitar dependência de scripts NCL;
   - manter nomes de saída compatíveis enquanto `psichi.py` ainda depender de pesos.

4. **Substituir `uv2sfvpf`**
   - avaliar formulação espectral/lat-lon equivalente;
   - documentar a convenção de sinal de `velocity_potential`, hoje preservada como `-1.0 * vp_cell`;
   - manter o fator `6371229.0/6371220.0` até validar cientificamente se ainda é necessário.

5. **Remover fronteira shell**
   - após substituir `weights.py` e `psichi.py`, remover ou limitar `external.py`;
   - o comando `mpasbflow all` deve executar sem `module load ncl`, sem `ncl`, sem `ncks`, sem `ncap2`, sem `ncrename` e sem `ncatted`.

## Critério de pronto

O BFLOW pode ser considerado Python puro quando:

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time YYYY-MM-DD_HH:MM:SS \
  --end-valid-time YYYY-MM-DD_HH:MM:SS \
  --valid-interval-hours 24 \
  --clean-output
```

rodar usando apenas bibliotecas Python e executáveis do próprio ambiente Python, produzindo `PTB_f48mf24.nc` numericamente compatível com o fluxo atual baseado em NCL.

# BFLOW Python backend notes

Esta nota documenta a remoção inicial do NCL nas etapas de pesos e conversão `u/v -> psi/chi`.

## O que mudou

- `bflow_core/weights.py` não gera mais arquivos de peso ESMF via NCL.
- Os pesos agora são gerados em Python e salvos em:

```text
ESMF_weights/bflow_regridding_weights.npz
```

- `bflow_core/psichi.py` não chama mais `uv2sfvpf` do NCL.
- A conversão agora é feita em Python com:
  - interpolação esférica por vizinhos mais próximos com peso inverso da distância;
  - grade auxiliar regular de 1 grau;
  - cálculo aproximado de divergência e vorticidade;
  - solução espectral periódica da equação de Poisson para `stream_function` e `velocity_potential`.

## Dependência nova

O backend Python requer `scipy`, usado em:

- `scipy.spatial.cKDTree` para construir pesos;
- `scipy.fft` para resolver a equação de Poisson aproximada.

## Importante

Esta mudança remove a dependência operacional do NCL, mas **não deve ser considerada cientificamente equivalente ao caminho antigo sem validação**.

O caminho antigo usava:

```text
NCL ESMF_regrid_gen_weights
NCL ESMF_regrid_with_weights
NCL uv2sfvpf
```

O caminho novo usa uma aproximação Python independente. Portanto, antes de usar os produtos em produção, é necessário comparar os campos finais contra um baseline NCL para pelo menos:

- `stream_function`;
- `velocity_potential`;
- `PTB_f48mf24.nc` final;
- impacto posterior em `VBAL`, `HDIAG`, `NICAS` e `SO`.

## Teste recomendado

Rodar o mesmo período curto usado no smoke BFLOW com o backend antigo e novo e comparar:

```bash
ncdiff old/PTB_f48mf24.nc new/PTB_f48mf24.nc diff.nc
ncks -H -C -v stream_function diff.nc | head
ncks -H -C -v velocity_potential diff.nc | head
```

Também é recomendável calcular estatísticas globais por variável:

- média;
- desvio padrão;
- RMSE;
- correlação espacial por nível vertical.

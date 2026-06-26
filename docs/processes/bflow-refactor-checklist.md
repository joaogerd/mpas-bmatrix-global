# Checklist BFLOW refactor

- [x] Reduzir `bflow.py` a entrypoint de compatibilidade.
- [x] Criar pacote `bflow_core`.
- [x] Separar modelo de dados e funções de tempo.
- [x] Separar leitura/escrita de manifesto.
- [x] Separar criação de workspace.
- [x] Mover adição de variáveis para módulo Python real.
- [x] Mover diferença NMC para módulo Python real.
- [x] Mover validação para módulo Python real.
- [x] Reimplementar template `template_PTB.nc` em Python.
- [x] Centralizar chamadas externas em `external.py`.
- [x] Isolar pesos ESMF em `weights.py`.
- [x] Isolar conversão `u/v -> psi/chi` em `psichi.py`.
- [ ] Validar no JACI com smoke de quatro amostras.
- [ ] Comparar numericamente contra fluxo anterior.
- [ ] Substituir NCL em `weights.py`.
- [ ] Substituir NCL em `psichi.py`.

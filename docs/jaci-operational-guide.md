# JACI INPE: resumo operacional de infraestrutura, filas e uso
![HPC](https://img.shields.io/badge/HPC-Supercomputador-blue)
![Runbook](https://img.shields.io/badge/Tipo-Quick%20Start-orange)
![Scheduler](https://img.shields.io/badge/Scheduler-PBS-red)
![CPTEC-INPE](https://img.shields.io/badge/CPTEC-INPE-brightgreen)

> Documento elaborado a partir do **Manual do Ambiente Jaci INPE**.  
> Consulta realizada em: **12 de junho de 2026**.  
> Objetivo: reunir, em um único arquivo, as informações principais para uso cotidiano da JACI, incluindo acesso, tipos de nós, filesystems, filas PBS, tempos máximos, submissão de jobs e comandos úteis.

---

## 1. Visão geral

A **JACI** é o ambiente de computação de alto desempenho, HPC, do INPE. O acesso interativo ocorre por nós de login chamados `ian`, enquanto a execução de cargas pesadas deve ser feita nos **nós computacionais** por meio do escalonador **PBS**.

Resumo da infraestrutura:

| Componente | Quantidade | Características principais | Uso recomendado |
|---|---:|---|---|
| Login nodes | 7 | `ian01` a `ian07`; 1.5 TB de RAM e 256 CPUs por máquina | Acesso SSH, edição, compilação, preparação de scripts e submissão de jobs |
| Compute nodes | 104 | 256 núcleos físicos e 512 threads por nó | Simulações e processamento intensivo via PBS |
| Aux nodes | 10 | 1.5 TB de RAM e 256 CPUs por nó | Pré-processamento, pós-processamento, análise e visualização |
| Filesystem de dados | Lustre em `/p` | Paralelo, compartilhado e de alto desempenho | Dados, programas, saídas, scripts e arquivos usados em jobs |

---

## 2. Acesso à JACI

O acesso é feito por SSH:

```bash
ssh usuario@jaci.cptec.inpe.br
```

Para acesso gráfico, use encaminhamento X11:

```bash
ssh -X usuario@jaci.cptec.inpe.br
# ou
ssh -Y usuario@jaci.cptec.inpe.br
```

Requisitos de acesso:

- estar conectado à rede do CPTEC; ou
- utilizar VPN para acesso remoto.

Após o login, o usuário é direcionado automaticamente para um dos nós interativos `ian01` a `ian07`. Para verificar em qual nó você está:

```bash
hostname
hostname -s
```

---

## 3. Tipos de nós

### 3.1 Login nodes

Os login nodes são os nós de acesso interativo. Eles devem ser usados para tarefas leves e administrativas.

Hostnames:

```text
ian01
ian02
ian03
ian04
ian05
ian06
ian07
```

Uso adequado:

- edição de scripts e códigos;
- compilação de programas;
- testes leves;
- submissão de jobs ao PBS;
- visualização de resultados;
- gerenciamento de arquivos.

Evite nos login nodes:

- simulações computacionais;
- processamento intensivo de dados;
- códigos que consomem muita CPU ou memória;
- processos de longa duração.

> Regra prática: se a tarefa é pesada ou longa, submeta via PBS para os compute nodes.

---

### 3.2 Compute nodes

Os compute nodes são os nós destinados ao processamento pesado. Eles **não são acessados diretamente por SSH**. O acesso ocorre somente via PBS.

Especificações:

| Recurso | Por nó | Total em 104 nós |
|---|---:|---:|
| Núcleos físicos | 256 | 26.624 |
| Threads | 512 | 53.248 |

Observações importantes:

- os compute nodes acessam o filesystem Lustre em `/p`;
- os compute nodes **não acessam** a área HOME em `/home2`;
- programas, dados de entrada, scripts e saídas de jobs devem estar em `/p`.

Fluxo típico:

```text
usuário -> SSH -> login node -> qsub -> PBS -> compute nodes -> /p
```

---

### 3.3 Aux nodes

Os aux nodes são servidores auxiliares recomendados para pré e pós-processamento.

Especificações:

| Recurso | Valor |
|---|---:|
| Quantidade | 10 nós |
| RAM por nó | 1.5 TB |
| CPUs por nó | 256 |

Uso recomendado:

- preparação de dados antes da simulação;
- processamento de resultados após jobs;
- conversão de formatos;
- análise exploratória;
- geração de gráficos e visualizações;
- tarefas que exigem muita memória, mas não necessariamente muitos cores em paralelo.

Evite usar aux nodes para:

- simulações computacionais pesadas;
- jobs de longa duração que devem ser escalonados;
- processamento fortemente paralelo que deve ir para compute nodes.

---

## 4. Filesystems e diretórios importantes

### 4.1 HOME

A área HOME é montada automaticamente no login:

```bash
/home2/usuario
```

Características:

| Característica | HOME |
|---|---|
| Caminho | `/home2/usuario` |
| Tamanho padrão | cerca de 50 GB |
| Backup | regular |
| Acesso pelos compute nodes | não |
| Uso recomendado | configurações, scripts pequenos, utilitários pessoais e documentação |

Verificar uso:

```bash
df -h .
```

Não use a HOME para dados de processamento, datasets grandes ou resultados de simulações, pois os compute nodes não acessam `/home2`.

---

### 4.2 Filesystem Lustre `/p`

A área de dados principal fica em:

```bash
/p/projetos/grupo
```

O caminho `/lustre` é um link simbólico para `/p`.

Características:

| Característica | Lustre `/p` |
|---|---|
| Tipo | filesystem paralelo Lustre |
| Acesso pelos compute nodes | sim |
| Acesso pelos login nodes | sim |
| Acesso pelos aux nodes | sim |
| Performance | alta |
| Quota | por grupo |
| Uso recomendado | dados, executáveis, scripts, entradas, saídas e arquivos temporários de processamento |

Verificar espaço:

```bash
df -h /p
```

Verificar quota do grupo:

```bash
lfs quota -g nome_do_grupo /p
```

Verificar striping de arquivo:

```bash
lfs getstripe arquivo
```

Configurar striping em diretório:

```bash
lfs setstripe -c 4 diretorio/
```

---

### 4.3 Diferença prática entre HOME e `/p`

| Aspecto | HOME `/home2` | Lustre `/p` |
|---|---|---|
| Acesso pelos compute nodes | não | sim |
| Performance | padrão | alta |
| Tipo | NFS/storage corporativo | Lustre paralelo |
| Backup | regular | limitado |
| Uso principal | configurações e pequenos scripts | processamento, dados e programas |

> Para jobs PBS, coloque tudo que será lido ou executado em `/p`.

---

## 5. Filas PBS disponíveis

A JACI usa o **PBS**, Portable Batch System, para gerenciar submissão e execução de jobs. As filas são organizadas por tipo de uso, quantidade de recursos e walltime máximo.

| Fila | Nós | CPUs totais | Tempo máximo | Uso principal | Observações |
|---|---:|---:|---:|---|---|
| `aux` | 10 | não informado na tabela de filas | não informado | Pré e pós-processamento | Usa os aux nodes, não os compute nodes regulares |
| `pesqmini` | 7 | 3.584 | 00:30:00 | Testes rápidos | Ideal para validação, smoke tests e jobs curtos |
| `pesqmidi` | 7 | 3.584 | 02:00:00 | Processamento médio | Simulações de média duração e análises intermediárias |
| `pesqhigh` | 20 | 10.240 | 06:00:00 | Pesquisa de alta prioridade | Simulações importantes e processamento prioritário |
| `pesqextra` | 30 | 15.360 | 08:00:00 | Processamento extenso | Simulações longas e jobs de maior duração |
| `oper` | 40 | 20.480 | 08:00:00 | Operacional | Pode ter restrição de acesso |
| `preoper` | 40 | 20.480 | 08:00:00 | Pré-operacional | Pode ter restrição de acesso |

### 5.1 Como escolher a fila

Critério por tempo estimado:

| Tempo estimado do job | Fila sugerida |
|---|---|
| Menos de 30 minutos | `pesqmini` |
| 30 minutos a 2 horas | `pesqmidi` |
| 2 a 6 horas | `pesqhigh` |
| 6 a 8 horas | `pesqextra` |
| Pré ou pós-processamento | `aux` |
| Rotina operacional | `oper` ou `preoper`, conforme permissão |

Boas práticas:

- comece testando em `pesqmini`;
- solicite apenas os recursos necessários;
- adicione uma margem de 10 a 20% ao walltime estimado;
- monitore seus jobs com `qstat`;
- jobs que excedem o walltime são terminados automaticamente.

---

## 6. Estrutura básica de script PBS

Template geral:

```bash
#!/bin/bash
#PBS -N nome_do_job
#PBS -q fila
#PBS -l select=X:ncpus=Y
#PBS -l walltime=HH:MM:SS
#PBS -j oe
#PBS -o /p/projetos/grupo/logs/job.out

cd /p/projetos/grupo

module load modulo/versao

./programa
```

Diretivas principais:

| Diretiva | Função |
|---|---|
| `#PBS -N nome_do_job` | Nome do job exibido no `qstat` |
| `#PBS -q fila` | Fila de submissão |
| `#PBS -l select=N:ncpus=M` | Solicita N nós e M CPUs por nó |
| `#PBS -l walltime=HH:MM:SS` | Tempo máximo de execução |
| `#PBS -j oe` | Junta stdout e stderr no mesmo arquivo |
| `#PBS -o arquivo.out` | Define arquivo de saída |
| `#PBS -e arquivo.err` | Define arquivo de erro, caso stdout e stderr sejam separados |

Cada compute node possui 256 núcleos físicos e 512 threads. Para jobs MPI, escolha `select` e `ncpus` de acordo com o tamanho da execução.

---

## 7. Exemplos de scripts PBS

### 7.1 Teste rápido em `pesqmini`

```bash
#!/bin/bash
#PBS -N teste_rapido
#PBS -q pesqmini
#PBS -l select=1:ncpus=64
#PBS -l walltime=00:15:00
#PBS -j oe
#PBS -o /p/projetos/grupo/logs/teste_rapido.out

cd /p/projetos/grupo

echo "Job: $PBS_JOBID"
echo "Host: $(hostname)"
echo "Início: $(date)"

./programa_teste

echo "Fim: $(date)"
```

### 7.2 Job OpenMP

```bash
#!/bin/bash
#PBS -N job_openmp
#PBS -q pesqmidi
#PBS -l select=1:ncpus=64
#PBS -l walltime=01:00:00
#PBS -j oe
#PBS -o /p/projetos/grupo/logs/openmp.out

cd /p/projetos/grupo

export OMP_NUM_THREADS=64
./programa_openmp
```

### 7.3 Job MPI

```bash
#!/bin/bash
#PBS -N job_mpi
#PBS -q pesqhigh
#PBS -l select=4:ncpus=256
#PBS -l walltime=04:00:00
#PBS -j oe
#PBS -o /p/projetos/grupo/logs/mpi.out

cd /p/projetos/grupo

module load cray-mpich/8.1.31
module load cray-pals/1.6.1

mpirun -np 1024 ./programa_mpi
```

---

## 8. Comandos úteis do PBS

### 8.1 Submissão

```bash
qsub script.pbs
qsub -N meu_job -q pesqhigh script.pbs
```

### 8.2 Monitoramento

```bash
# Listar seus jobs
qstat
qstat -u $USER

# Listar todos os jobs
qstat -a

# Detalhes de um job
qstat -f JOB_ID

# Histórico de job
qstat -x JOB_ID

# Monitorar em tempo real
watch -n 5 qstat
```

### 8.3 Controle

```bash
# Cancelar job
qdel JOB_ID

# Segurar job
qhold JOB_ID

# Liberar job
qrls JOB_ID
```

### 8.4 Informações do sistema

```bash
# Ver filas
qstat -Q

# Ver jobs em uma fila específica
qstat -q pesqhigh

# Ver todos os nodes
pbsnodes -a

# Ver nodes livres
pbsnodes -l free
```

### 8.5 Estados de job no `qstat`

| Estado | Significado |
|---|---|
| `Q` | queued, aguardando na fila |
| `R` | running, executando |
| `H` | held, suspenso |
| `C` | completed, concluído |
| `E` | exiting, finalizando |

---

## 9. Variáveis úteis do PBS

O PBS define algumas variáveis de ambiente úteis dentro do job:

| Variável | Significado |
|---|---|
| `$PBS_JOBID` | ID do job |
| `$PBS_JOBNAME` | Nome do job |
| `$PBS_O_WORKDIR` | Diretório de onde o job foi submetido |
| `$PBS_NODEFILE` | Arquivo com a lista de nós alocados |
| `$PBS_QUEUE` | Fila do job |

Uso recomendado para iniciar no diretório de submissão:

```bash
cd $PBS_O_WORKDIR
```

Exemplo para registrar informações do job:

```bash
echo "Job ID: $PBS_JOBID"
echo "Nome do job: $PBS_JOBNAME"
echo "Diretório de submissão: $PBS_O_WORKDIR"
echo "Nodefile: $PBS_NODEFILE"
echo "Fila: $PBS_QUEUE"
```

---

## 10. Módulos

Comandos básicos:

```bash
# Listar módulos disponíveis
module avail

# Buscar módulo
module spider gcc

# Carregar módulo
module load gcc/9.3.0

# Listar módulos carregados
module list

# Descarregar módulo
module unload gcc

# Limpar todos os módulos
module purge
```

Exemplo em script PBS:

```bash
module purge
module load cray-mpich/8.1.31
module load cray-pals/1.6.1

mpirun ./meu_programa
```

---

## 11. Configuração de ambiente

Como a HOME é compartilhada entre diferentes ambientes do CPTEC, a documentação recomenda separar configurações específicas da JACI.

Arquivos sugeridos:

```text
$HOME/
├── .bash_profile       # arquivo principal, detecta o ambiente
├── .profile.jaci       # profile específico para JACI
├── .bashrc.jaci        # bashrc específico para JACI
├── .profile            # profile para outros ambientes
└── .bashrc             # bashrc para outros ambientes
```

Exemplo de lógica no `.bash_profile`:

```bash
HOSTNAME=$(hostname -s)

if [[ $HOSTNAME = jaci0* ]] || [[ $HOSTNAME = ian0* ]]; then
    . "$HOME/.profile.jaci"
    . "$HOME/.bashrc.jaci"
else
    . "$HOME/.profile"
    . "$HOME/.bashrc"
fi
```

Templates oficiais podem ser encontrados em:

```bash
/p/configs-jaci/
# ou
/lustre/configs-jaci/
```

Copiar templates:

```bash
cd ~
cp .bash_profile .bash_profile.backup
cp .bashrc .bashrc.backup
cp .profile .profile.backup

cp /p/configs-jaci/.bash_profile ~/
cp /p/configs-jaci/.bashrc.jaci ~/
cp /p/configs-jaci/.profile.jaci ~/
```

---

## 12. Problemas comuns e soluções rápidas

| Problema | Causa provável | Solução sugerida |
|---|---|---|
| Job não encontra arquivos | Arquivos estão em `/home2` | Mover programas, dados e scripts para `/p` |
| Variáveis do `.bashrc.jaci` não aparecem no job | Jobs PBS não carregam `.bashrc` por padrão | Definir variáveis no próprio PBS ou usar `source /p/projetos/grupo/.env.jaci` |
| Módulo não carrega | Sistema de módulos não inicializado ou `MODULEPATH` incorreto | Usar `module purge`, checar `module avail` e carregar módulos explicitamente |
| Conda ativa ambiente errado | Configuração global da HOME sendo carregada | Separar `.condarc` ou configurar `auto_activate_base: false` |
| PATH mistura ambientes | `.bashrc` global compartilhado | Limpar e redefinir PATH em `.bashrc.jaci` |
| Login muito lento | Muitos módulos ou comandos pesados no `.bashrc` | Usar carregamento sob demanda e reduzir inicialização automática |
| Quota excedida | Dados/cache acumulados | Limpar arquivos antigos e mover caches para `/p` |

---

## 13. Checklist antes de submeter um job

Antes de rodar:

- [ ] O script PBS está em `/p/projetos/grupo` ou acessa apenas arquivos em `/p`.
- [ ] Dados de entrada estão em `/p`.
- [ ] Executáveis estão em `/p`.
- [ ] Diretório de logs existe.
- [ ] A fila escolhida é compatível com o walltime.
- [ ] `select` e `ncpus` foram definidos de forma coerente.
- [ ] Módulos necessários são carregados dentro do script PBS.
- [ ] Variáveis de ambiente necessárias são definidas no script ou em arquivo carregado explicitamente.
- [ ] O job foi testado primeiro em `pesqmini`, quando possível.

Exemplo de criação de estrutura:

```bash
cd /p/projetos/grupo
mkdir -p logs scripts data output
```

---

## 14. Estrutura de diretórios recomendada

```text
/p/projetos/grupo/
├── dados/
│   ├── input/
│   └── output/
├── programas/
│   ├── src/
│   └── bin/
├── scripts/
│   ├── pbs/
│   ├── preprocessing/
│   └── postprocessing/
├── logs/
└── scratch/
```

Para a HOME:

```text
~/
├── bin/        # scripts pessoais pequenos
├── docs/       # documentação
├── configs/    # configurações
└── utils/      # utilitários leves
```

---

## 15. Referências consultadas

- Manual do Ambiente Jaci INPE, página inicial: `https://www.cptec.inpe.br/coids/docs/jaci/`
- Conexão SSH: `https://www.cptec.inpe.br/coids/docs/jaci/acesso/conexao/`
- Login Nodes: `https://www.cptec.inpe.br/coids/docs/jaci/acesso/login-nodes/`
- Área HOME: `https://www.cptec.inpe.br/coids/docs/jaci/acesso/home/`
- Filesystem de Dados: `https://www.cptec.inpe.br/coids/docs/jaci/infraestrutura/filesystem/`
- Aux Nodes: `https://www.cptec.inpe.br/coids/docs/jaci/infraestrutura/aux-nodes/`
- Nodes Computacionais: `https://www.cptec.inpe.br/coids/docs/jaci/infraestrutura/compute-nodes/`
- Filas Disponíveis: `https://www.cptec.inpe.br/coids/docs/jaci/jobs/filas/`
- Submissão de Jobs: `https://www.cptec.inpe.br/coids/docs/jaci/jobs/submissao/`
- Referência Rápida: `https://www.cptec.inpe.br/coids/docs/jaci/referencia/`
- Problemas Comuns: `https://www.cptec.inpe.br/coids/docs/jaci/configuracao/problemas/`

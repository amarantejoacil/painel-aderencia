# Documentação Funcional — Painel de Aderência de Atividades

## 1. O que é o sistema

O **Painel de Aderência de Atividades** é uma aplicação web que apoia a conferência dos lançamentos de Tasks do **Azure Boards**. Ele consolida os registros por **colaborador e por dia**, aplica as regras de carga horária definidas pela equipe e apresenta indicadores e pendências em um dashboard mensal.

O foco do sistema é verificar se os lançamentos estão **aderentes à carga esperada** — não medir produtividade individual.

**Principais telas:** Dashboard, Relatório de Inconsistências, Importação, Colaboradores, Calendário e Configurações (integração Azure DevOps).

---

## 2. Problema que resolve

Antes do painel, a equipe dependia de processos manuais que geravam retrabalho e inconsistências:

| Dificuldade | Situação anterior |
|---|---|
| Conferência manual de CSV | Abrir planilhas exportadas do Azure Boards e revisar linha a linha |
| Sincronização com o Azure | Baixar relatório manualmente sempre que precisava atualizar o mês |
| Análise por colaborador | Verificar horas de cada pessoa separadamente, dia a dia |
| Dias sem lançamento | Identificar manualmente dias úteis sem nenhuma Task registrada |
| Horas incompletas ou excedentes | Comparar manualmente o executado com a carga esperada |
| Regras de calendário | Considerar data de entrada, saída, feriados, pontos facultativos e dias úteis |
| Pessoas fora da equipe no export | Responsáveis de outras áreas apareciam no arquivo e poluíam a análise |

O sistema automatiza a conferência, permite **importar via CSV ou sincronizar pela API do Azure DevOps**, centraliza a visão da equipe e reduz o esforço operacional da gestão.

---

## 3. Como funciona

### Visão geral do fluxo

```
Azure Boards  →  CSV (export manual)  ou  API (sincronização)  →  Importação  →  Lote em uso  →  Regras de negócio  →  Dashboard / Relatórios
```

1. **Azure Boards** — A equipe registra Tasks no Azure DevOps/Azure Boards.
2. **Entrada de dados** — Por **CSV** (Relatório Contrato ou equivalente) ou por **Sincronizar Azure DevOps** na tela de Importação (mês/ano escolhidos).
3. **Processamento** — O sistema lê Tasks, identifica responsável, data de referência, horas (quando existirem), estado, projeto e atividade; vincula ao cadastro da equipe pelo nome no Azure.
4. **Lote em uso no painel** — O dashboard e os relatórios usam sempre o **último lote de importação** gravado (histórico de lotes anteriores permanece consultável na Importação).
5. **Regras de negócio** — Para cada colaborador elegível e cada dia do mês, calcula horas esperadas, horas executadas e classifica o status do dia.
6. **Dashboard e relatórios** — Indicadores consolidados, filtros, detalhe por colaborador, exportação Excel, texto de observações do período e relatório de inconsistências.

### Importação CSV

- Envio por seleção ou arrastar e soltar.
- Confirmação do **mês/ano de referência** (útil quando o CSV abrange mais de um mês).
- Validação das colunas esperadas (incluindo **Data referência**, **Assigned To**, **State** e, quando existir, **Atividade**).
- Cada importação CSV gera um **novo lote** com as linhas daquele arquivo; esse lote passa a ser o **em uso no painel** (substitui o conjunto anterior exibido na análise).
- É possível **excluir** um lote pelo histórico (remove o lote e as atividades vinculadas).

### Sincronização Azure DevOps (API)

- Configuração em **Configurações**: URL base, organização, projeto, PAT (token só no servidor), campos customizados TJMT quando aplicável.
- Na Importação, escolhe-se **mês e ano** e clica-se em **Sincronizar Azure DevOps**.
- **Prévia antes de importar:** abre um popup com responsáveis encontrados no Azure, quantidade de Tasks e vínculo com colaborador cadastrado. É possível **excluir responsáveis** da importação (linhas destacadas em vermelho = **não serão importadas**). Ao confirmar, a exclusão vale para aquele sync e as **regras de exclusão ficam salvas** para sincronizações futuras.
- Tasks de responsáveis excluídos **não entram no lote**; colaboradores cujo nome no Azure (ou nome cadastrado) conste na lista de excluídos **não aparecem na análise** do dashboard, mesmo que existam Tasks antigas no banco.
- A sincronização **mescla** Tasks pelo **ID da Task**: parte do último lote já gravado, atualiza/sobrescreve pelo que veio do Azure no período e grava um **novo lote** (origem `azure_api`). Tasks fora do mês sincronizado são ignoradas com aviso.
- Tasks com dados inválidos ou incompletos no mapeamento (sem data utilizável etc.) são **ignoradas** e contabilizadas na prévia/resumo.
- Campos prioritários na API (projeto TJMT): data em campo customizado de referência, horas executadas/estimadas e categoria de atividade customizada, além de título, responsável e estado.

### Histórico de importações

- Lista lotes CSV e Azure com período, contagem de linhas, mapeadas, avisos e indicação **Em uso no painel** (último lote).
- Re-sincronizar o mesmo mês substitui o conjunto analisado pelo novo merge, mantendo histórico de execuções anteriores.

---

## 4. Regras de negócio

As regras abaixo refletem o comportamento **implementado** no sistema.

### Carga horária diária

- Cada colaborador possui uma **carga diária** configurável no cadastro (padrão: **8 horas**).
- Essa carga define quantas horas são esperadas em cada dia útil obrigatório.

### Dias obrigatórios e dias livres

| Situação | Exige lançamento? | Status típico |
|---|---|---|
| Segunda a sexta (dia útil) | Sim | Regular, Incompleto, Sem lançamento ou Excedente |
| Sábado e domingo | Não | Não exigido |
| Feriado cadastrado | Não | Não exigido |
| Ponto facultativo cadastrado | Não | Não exigido |
| Liberação de expediente (calendário) | Não | Não exigido |
| Antes da data de entrada do colaborador | Não | Não exigido |
| A partir da data de saída do colaborador (inclusive) | Não | Não exigido / Desligado |
| Data futura (após hoje) | Não | Não exigido |
| Ausência justificada cadastrada no colaborador | Não (naquele dia) | Ausência justificada |

### Ausências do colaborador

- No detalhe do colaborador é possível registrar **ausências** (atestado, férias, folga, licença, liberação de expediente, outro) com intervalo de datas e observação.
- Em dia útil que seria obrigatório, se houver ausência cadastrada cobrindo a data, o dia fica como **Ausência justificada** (não conta como pendência de lançamento). Tasks do dia, se existirem, continuam visíveis no detalhe.

### Soma de Tasks no mesmo dia

- Várias Tasks do **mesmo colaborador no mesmo dia** são **somadas** para o executado do dia.
- Exemplo: 3h + 5h no mesmo dia = **8h executadas** → dia **Regular** (com carga de 8h).

### Horas esperadas × horas executadas

- **Esperado** — Carga diária do colaborador, quando o dia exige lançamento.
- **Executado** — Soma das horas efetivas das Tasks daquele dia, conforme a regra abaixo.

**Ordem de cálculo das horas de cada Task (Azure / CSV com horas):**

1. Se houver **horas executadas** registradas e maiores que zero, usa esse valor.
2. Se a Task estiver em **estado concluído** no Azure e não houver horas executadas, usa **horas estimadas** (se houver) ou, na falta delas, a **carga diária** do colaborador.
3. Se não estiver concluída e não houver horas executadas positivas, usa estimada quando existir; caso contrário **0h** para aquela Task na soma.

**Presença no dia (aderência):** se no dia existir ao menos uma Task vinculada ao colaborador e **nenhuma** Task contribuir com horas mensuráveis pela regra acima (typical: Tasks abertas sem horas), o dia é tratado como **presença**: executado = **carga diária completa** (equivalente ao CSV sem coluna de horas).

**Modo horas registradas:** quando há horas executadas (ou concluídas com estimada/carga), o sistema soma os valores reais/equivalentes e classifica Regular, Incompleto, Excedente ou Sem lançamento.

**Tasks não concluídas:** estados como *Novo* ou *Em andamento* **não impedem** a aderência quando há presença ou horas; aparecem como **alerta informativo** no Relatório de Inconsistências (Tasks em aberto no mês), sem bloquear o status do dia por si só.

### Horas excedentes não compensam outros dias

- A análise é **sempre por colaborador e por dia**.
- Horas a mais em um dia **não reduzem** pendências de outro dia.
- Exemplo: 16h na terça não elimina um dia incompleto ou sem lançamento na quarta.

### Status do dia

| Status | Quando ocorre |
|---|---|
| **Regular** | Dia exige lançamento e as horas executadas são **iguais** às esperadas |
| **Incompleto** | Dia exige lançamento e as horas executadas são **menores** que as esperadas |
| **Sem lançamento** | Dia exige lançamento e **não há Tasks** (ou horas efetivas = 0 sem regra de presença) |
| **Excedente** | Dia exige lançamento e as horas executadas são **maiores** que as esperadas |
| **Não exigido** | Fim de semana, feriado, ponto facultativo, liberação, fora do período do colaborador ou data futura |
| **Ausência justificada** | Dia seria obrigatório, mas há ausência cadastrada para a data |

### Colaboradores considerados na análise

Entram no dashboard apenas colaboradores que:

- estão marcados como **ativos**;
- já tinham entrado antes do fim do mês analisado;
- ainda não tinham saído antes do início do mês analisado (quando há data de saída);
- **não** estão na lista de **responsáveis excluídos** da sincronização Azure (regra salva ao marcar exclusão na prévia).

Colaboradores **inativos** ou **desligados** no período seguem regras de data de saída; desligamento pode ser registrado no cadastro.

### Vínculo com o Azure

- O responsável (`Assigned To` no CSV ou campo equivalente na API) é comparado ao **nome cadastrado no Azure** de cada colaborador (normalização de nome).
- Tasks de responsáveis **sem cadastro** podem ser importadas, mas geram aviso e **não entram** na análise daquele colaborador (sem vínculo).
- Responsáveis **explicitamente excluídos** na prévia da sync não têm Tasks importadas nas execuções em que a regra é aplicada e não entram como colaboradores analisados se o nome coincidir com o cadastro ou nome no Azure.

---

## 5. Aderência de Horas

### Conceito

**Aderência de Horas** mede o quanto os registros importados se aproximam da carga esperada no período. É um indicador de **conformidade dos lançamentos**, não de produtividade ou desempenho individual.

### Como o percentual é calculado

Para cada dia com carga esperada, o sistema considera apenas até o limite esperado:

```
Contribuição do dia = menor valor entre (horas executadas, horas esperadas)
```

No mês:

```
Aderência (%) = (soma das contribuições dos dias ÷ soma das horas esperadas) × 100
```

**Regras importantes:**

- Horas excedentes **entram no total executado**, mas **não elevam** a aderência acima de **100%**.
- Horas faltantes em um dia **não são compensadas** por excedentes de outro dia.
- Dias com **ausência justificada** não entram na soma de esperado/executado da aderência da mesma forma que dias obrigatórios pendentes.
- No dashboard da equipe, o cálculo consolida todos os colaboradores analisados no mês selecionado.

**Exemplo simplificado:** colaborador com 20 dias úteis de 8h (160h esperadas). Se em todos os dias lançou 8h, a aderência é **100%**. Se em um dia lançou 16h e em outro 0h, a aderência considera 8h + 0h nesses dias — **não** 16h compensando o dia vazio.

---

## 6. Funcionalidades

### Dashboard (Aderência de Horas)

- Visão mensal da equipe com indicadores, gráficos, tabela por colaborador e filtros por mês, ano, colaborador e status.
- Texto explicativo: a conferência é **por colaborador e por dia**; horas a mais em um dia **não compensam** outro.
- Ações:
  - **Relatório de Inconsistências** — abre o relatório do mesmo período.
  - **Exportar Excel** — planilha de atividades do mês (Tasks, datas, horas, estado, atividade, contexto de calendário/ausências quando aplicável).
  - **Texto para o relatório** — gera texto consolidado de observações do período (feriados, liberações, ausências da equipe etc.) para colar em relatórios externos.
- Acesso ao **detalhe** de cada colaborador pelo nome na tabela.

### Relatório de Inconsistências

- Lista colaboradores do mês com situação **OK** ou **Pendências**.
- Para pendências: dias **sem lançamento**, **incompletos** ou **excedentes**, com texto resumido e detalhe das Tasks do dia.
- **Verificação de lançamento** em dias sem lançamento: distingue “nenhuma Task na importação” vs “Tasks existem mas horas insuficientes”.
- **Tasks não concluídas** no mês (estado diferente de concluído): seção de alerta; não substitui a classificação do dia, mas apoia a conferência no Azure.
- Filtros por situação e tipo de pendência; exportação quando disponível na API do relatório.

### Importação

- **CSV** — fluxo com pré-visualização, confirmação de período e avisos de mapeamento.
- **Azure DevOps** — status da integração, última sincronização, escolha de mês/ano, aviso se já existir lote do período, **prévia com exclusão de responsáveis** e confirmação.
- Histórico unificado de lotes (origem CSV ou Azure) com exclusão por lote.

### Configurações (Azure DevOps)

- Credenciais e projeto; teste de conexão; descoberta/amostra de campos de Work Item; lista de projetos quando configurado.
- Campos descobertos na sync podem ser persistidos para mapeamento consistente (data, horas, atividade).

### Colaboradores

Cadastro e edição de:

- nome;
- nome utilizado no Azure;
- data de entrada e saída;
- carga diária;
- situação (ativo/inativo);
- **desligamento** (data de saída);
- **ausências** por intervalo (no detalhe do colaborador).

### Calendário

Cadastro de **feriados**, **pontos facultativos** e **liberações de expediente**, com data, tipo e descrição. Dias cadastrados não geram exigência de lançamento. Exceções podem ser editadas ou removidas.

### Filtros do Dashboard

| Filtro | Função |
|---|---|
| Mês / Ano | Período analisado |
| Colaborador | Restringe a visão a uma pessoa |
| Status | Mostra colaboradores que possuem **ao menos um dia** com o status selecionado |

### Detalhamento por colaborador

Visão mensal da pessoa com:

- resumo de horas esperadas, executadas e aderência;
- tabela dia a dia com status (inclui ausência justificada e fins de semana destacados);
- painel com as **Tasks** do dia selecionado (ID, título, horas, estado, projeto, atividade);
- gestão de **ausências** no período.

---

## 7. Indicadores do Dashboard

| Indicador | O que representa |
|---|---|
| **Colaboradores analisados** | Quantidade de colaboradores elegíveis incluídos no mês (ativos no período, não excluídos por regra Azure) |
| **Horas esperadas** | Soma da carga diária em todos os dias úteis obrigatórios da equipe |
| **Horas executadas** | Soma real (ou equivalente em modo presença) de todos os lançamentos importados do lote em uso |
| **Aderência de Horas** | Percentual de conformidade, limitado a 100% |
| **Dias regulares** | Dias em que a carga foi atendida integralmente |
| **Dias incompletos** | Dias com lançamento abaixo da carga esperada |
| **Dias sem lançamento** | Dias úteis obrigatórios sem lançamento adequado |
| **Dias excedentes** | Dias com lançamento acima da carga esperada |

Na tabela por colaborador também são exibidos, para cada pessoa: horas esperadas, executadas, aderência e contagem de dias sem lançamento, incompletos e excedentes.

O dashboard pode exibir ainda indicadores derivados (cobertura de lançamentos, colaboradores sem pendências no mês etc.) com base nos mesmos dados.

---

## 8. Exemplo simples

Considerando carga diária de **8 horas** em um dia útil obrigatório:

| Horas executadas | Status |
|---|---|
| 8h | Regular |
| 5h | Incompleto |
| 0h (sem Tasks) | Sem lançamento |
| 10h | Excedente |

**Complemento — múltiplas Tasks no mesmo dia:**

| Tasks do dia | Total | Status |
|---|---|---|
| 3h + 5h | 8h | Regular |
| 2h + 2h | 4h | Incompleto |
| Task(s) no dia sem horas mensuráveis (presença) | 8h* | Regular |

\* Presença: ao menos uma Task no dia obrigatório, sem horas que entrem na soma, equivale à carga diária completa.

**Exclusão na sync Azure:** se “Paula” e “Bruno” forem marcados como **não importar** na prévia, as Tasks deles não entram no novo lote e eles deixam de ser listados como colaboradores analisados quando seus nomes coincidem com a regra salva.

---

## 9. Benefícios

- **Redução da conferência manual** — substitui a revisão linha a linha do CSV e permite sync direta com o Azure.
- **Controle do escopo da equipe** — exclusão de responsáveis indesejados na prévia, com regra persistente.
- **Identificação rápida de inconsistências** — dashboard, relatório dedicado e verificação de dias sem lançamento.
- **Visão consolidada da equipe** — indicadores, gráficos e tabela única por mês.
- **Padronização da análise** — mesmas regras aplicadas a todos os colaboradores elegíveis.
- **Apoio à gestão e relatórios** — exportação Excel e texto de observações do período.
- **Rastreabilidade** — histórico de importações CSV e Azure por mês.

---

## 10. Referência técnica (resumo)

| Item | Detalhe |
|---|---|
| Interface | Aplicação web (React); API REST (FastAPI); banco PostgreSQL |
| Execução recomendada | Docker Compose (frontend + API + banco) |
| Origem dos dados | `csv` ou `azure_api` por lote de importação |
| Análise | Motor em `backend/app/analysis/engine.py`; contexto carrega último lote e colaboradores elegíveis |
| Integração Azure | Endpoints sob `/api/azure-devops` (status, teste, prévia, sync); configuração em `/api/settings/azure-devops` |

Para instalação, CSV de exemplo e comandos de teste, consulte o [README.md](./README.md) do repositório.

---

## 11. Indicadores do acompanhamento de projetos

A tela de Sprints mede cada Sprint isoladamente. Os totais dos relatórios de projeto contam cada história uma vez quando ela aparece em mais de uma Sprint. As linhas de cada Sprint continuam podendo repetir a história, porque descrevem o recorte daquela Sprint.

| Indicador | Critério |
|---|---|
| Histórias da Sprint | Pelas revisões, estava na Sprint no corte, foi criada nela ou foi concluída nela. Itens Removed ficam de fora. Fuso America/Cuiaba. |
| Histórias criadas | Data de criação dentro do intervalo completo da Sprint. No período, uma vez se ocorreu em qualquer Sprint do recorte. |
| Histórias concluídas | Transição para Closed, Resolved ou Done dentro do intervalo, lida nas revisões. O estado atual sozinho não prova a conclusão daquela Sprint. No período, uma vez se a transição ocorreu em qualquer Sprint. |
| Histórias em andamento | No corte, estado Active, New ou In Progress, sem conclusão no intervalo. No período, somente se não houve conclusão em nenhuma Sprint e o corte da Sprint mais recente é de andamento. |
| Histórias pendentes | No corte, nem concluídas no intervalo nem em andamento. Estado já concluído sem transição dentro da Sprint não entra em pendentes. No período, vale o corte da Sprint mais recente, salvo conclusão em alguma Sprint. |
| Adicionadas após o início | Estava na Sprint no corte, não estava no início e não foi criada na Sprint. No período, uma vez. |
| Impedimentos no relatório | Campo explícito da história nas histórias das Sprints do período. Vazio, «não» e «none» não contam. A mesma história conta uma vez. A visão geral do módulo continua com a leitura anterior desse campo na área. |

A tela de Sprints não usa Committed, Approved nem Doing como andamento. A análise inteligente de Sprints usa um conjunto mais amplo e, nos impedimentos, também lê tags e comentários. Essas regras da análise permanecem.

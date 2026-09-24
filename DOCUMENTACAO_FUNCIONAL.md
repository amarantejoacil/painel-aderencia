# Documentação Funcional — Painel de Aderência de Atividades

## 1. O que é o sistema

O **Painel de Aderência de Atividades** é uma aplicação web que apoia a conferência dos lançamentos de Tasks exportados do **Azure Boards**. Ele consolida os registros por **colaborador e por dia**, aplica as regras de carga horária definidas pela equipe e apresenta indicadores e pendências em um dashboard mensal.

O foco do sistema é verificar se os lançamentos estão **aderentes à carga esperada** — não medir produtividade individual.

---

## 2. Problema que resolve

Antes do painel, a equipe dependia de processos manuais que geravam retrabalho e inconsistências:

| Dificuldade | Situação anterior |
|---|---|
| Conferência manual de CSV | Abrir planilhas exportadas do Azure Boards e revisar linha a linha |
| Análise por colaborador | Verificar horas de cada pessoa separadamente, dia a dia |
| Dias sem lançamento | Identificar manualmente dias úteis sem nenhuma Task registrada |
| Horas incompletas ou excedentes | Comparar manualmente o executado com a carga esperada |
| Regras de calendário | Considerar data de entrada, saída, feriados, pontos facultativos e dias úteis |

O sistema automatiza essa conferência, centraliza a visão da equipe e reduz o esforço operacional da gestão.

---

## 3. Como funciona

O fluxo principal do sistema segue estas etapas:

```
Azure Boards  →  Exportação CSV  →  Importação  →  Processamento  →  Regras de negócio  →  Dashboard
```

1. **Azure Boards** — A equipe registra Tasks no Azure DevOps/Azure Boards.
2. **Exportação CSV** — É gerado o arquivo do Relatório Contrato (ou equivalente) com as colunas esperadas.
3. **Importação** — O arquivo é enviado pela tela de Importação. Cada nova importação **substitui a anterior**.
4. **Processamento** — O sistema lê as linhas do CSV, identifica colaborador, data e horas (quando existirem) e vincula ao cadastro da equipe.
5. **Regras de negócio** — Para cada colaborador e cada dia do mês, calcula horas esperadas, horas executadas e classifica o status do dia.
6. **Dashboard** — Exibe indicadores consolidados, filtros e detalhamento por colaborador e por Task.

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
| Antes da data de entrada do colaborador | Não | Não exigido |
| A partir da data de saída do colaborador (inclusive) | Não | Não exigido / Desligado |
| Data futura (após hoje) | Não | Não exigido |

### Soma de Tasks no mesmo dia

- Várias Tasks do **mesmo colaborador no mesmo dia** são **somadas**.
- Exemplo: 3h + 5h no mesmo dia = **8h executadas** → dia **Regular** (com carga de 8h).

### Horas esperadas × horas executadas

- **Esperado** — Carga diária do colaborador, quando o dia exige lançamento.
- **Executado** — Soma das horas das Tasks daquele dia, ou valor equivalente no modo presença (ver abaixo).

**Modo presença:** quando o CSV **não possui coluna de horas**, se houver ao menos uma Task no dia obrigatório, o sistema considera o dia com a **carga diária completa** do colaborador.

**Modo horas registradas:** quando o CSV traz coluna de horas (`Completed Work`, `Horas executadas` etc.), o sistema soma os valores reais informados.

### Horas excedentes não compensam outros dias

- A análise é **sempre por colaborador e por dia**.
- Horas a mais em um dia **não reduzem** pendências de outro dia.
- Exemplo: 16h na terça não elimina um dia incompleto ou sem lançamento na quarta.

### Status do dia

| Status | Quando ocorre |
|---|---|
| **Regular** | Dia exige lançamento e as horas executadas são **iguais** às esperadas |
| **Incompleto** | Dia exige lançamento e as horas executadas são **menores** que as esperadas |
| **Sem lançamento** | Dia exige lançamento e **não há Tasks** (ou horas = 0) |
| **Excedente** | Dia exige lançamento e as horas executadas são **maiores** que as esperadas |
| **Não exigido** | Fim de semana, feriado, ponto facultativo, fora do período do colaborador ou data futura |

### Colaboradores considerados na análise

Entram no dashboard apenas colaboradores que:

- estão marcados como **ativos**;
- já tinham entrado antes do fim do mês analisado;
- ainda não tinham saído antes do início do mês analisado (quando há data de saída).

### Vínculo com o Azure

- O responsável no CSV (`Assigned To`) é comparado ao **nome cadastrado no Azure** de cada colaborador.
- Tasks de responsáveis não cadastrados são importadas, mas geram aviso e **não entram** na análise daquele colaborador.

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
- No dashboard da equipe, o cálculo consolida todos os colaboradores analisados no mês selecionado.

**Exemplo simplificado:** colaborador com 20 dias úteis de 8h (160h esperadas). Se em todos os dias lançou 8h, a aderência é **100%**. Se em um dia lançou 16h e em outro 0h, a aderência considera 8h + 0h nesses dias — **não** 16h compensando o dia vazio.

---

## 6. Funcionalidades

### Dashboard

Visão mensal da equipe com indicadores, tabela por colaborador e filtros por mês, ano, colaborador e status. Permite acessar o detalhe de cada pessoa.

### Importação de CSV

- Envio de arquivo por seleção ou arrastar e soltar.
- Validação das colunas obrigatórias do Relatório Contrato.
- Exibição de resumo (linhas válidas, mapeadas, sem cadastro) e avisos.
- **Nova importação substitui a anterior.**
- **Exclusão da importação** — remove o lote e todas as atividades vinculadas.

### Colaboradores

Cadastro e edição de:

- nome;
- nome utilizado no Azure;
- data de entrada e saída;
- carga diária;
- situação (ativo/inativo).

### Calendário

Cadastro de **feriados** e **pontos facultativos**, com data, tipo e descrição. Dias cadastrados não geram exigência de lançamento. Exceções podem ser removidas.

### Filtros do Dashboard

| Filtro | Função |
|---|---|
| Mês / Ano | Período analisado |
| Colaborador | Restringe a visão a uma pessoa |
| Status | Mostra colaboradores que possuem **ao menos um dia** com o status selecionado |

### Detalhamento por colaborador

Ao clicar no nome no dashboard, abre-se a visão mensal da pessoa com:

- resumo de horas esperadas, executadas e aderência;
- tabela dia a dia com status;
- painel lateral com as **Tasks** do dia selecionado (ID, título, horas, estado).

---

## 7. Indicadores do Dashboard

| Indicador | O que representa |
|---|---|
| **Colaboradores analisados** | Quantidade de colaboradores ativos incluídos no mês |
| **Horas esperadas** | Soma da carga diária em todos os dias úteis obrigatórios da equipe |
| **Horas executadas** | Soma real (ou equivalente em modo presença) de todos os lançamentos |
| **Aderência de Horas** | Percentual de conformidade, limitado a 100% |
| **Dias regulares** | Dias em que a carga foi atendida integralmente |
| **Dias incompletos** | Dias com lançamento abaixo da carga esperada |
| **Dias sem lançamento** | Dias úteis obrigatórios sem nenhuma Task |
| **Dias excedentes** | Dias com lançamento acima da carga esperada |

Na tabela por colaborador também são exibidos, para cada pessoa: horas esperadas, executadas, aderência e contagem de dias sem lançamento, incompletos e excedentes.

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
| Task sem hora informada (modo presença) | 8h* | Regular |

\* No modo presença, a presença de ao menos uma Task equivale à carga diária completa.

---

## 9. Benefícios

- **Redução da conferência manual** — substitui a revisão linha a linha do CSV.
- **Identificação rápida de inconsistências** — destaca dias sem lançamento, incompletos e excedentes.
- **Visão consolidada da equipe** — indicadores e tabela única por mês.
- **Padronização da análise** — mesmas regras aplicadas a todos os colaboradores.
- **Apoio à gestão** — base objetiva para acompanhar aderência dos registros no Azure Boards.

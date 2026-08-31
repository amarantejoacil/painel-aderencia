# Painel de Aderência de Atividades

Aplicação web para conferir lançamentos de Tasks exportados do Azure Boards. A análise é sempre por **colaborador + data**: a soma das horas de um dia não compensa outro dia.

O indicador principal é **Aderência de Horas**. Horas excedentes entram no executado, mas não elevam o percentual acima de 100%.

## O que o sistema faz

1. Cadastro de colaboradores (nome, nome no Azure, entrada, saída, carga diária).
2. Cadastro de feriados e pontos facultativos.
3. Importação do CSV do Relatório Contrato.
4. Dashboard mensal com filtros, resumo da equipe e detalhe por dia e por Task.

## CSV esperado

O export real do Boards usado pela equipe tem estas colunas:

`Work Item Type, ID, Data referência, Title, Assigned To, State`

- A data da atividade vem de **Data referência** (`dd/mm/aaaa hh:mm:ss`).
- O responsável vem de **Assigned To** no formato `Nome Completo <PJMT\matricula>`. O cadastro deve usar o nome, sem a matrícula.
- Este arquivo **não traz horas**. Quando não houver coluna de horas, o sistema usa o **modo presença**: se existir ao menos uma Task no dia obrigatório, o dia é Regular com a carga diária do colaborador.
- Se o CSV trouxer `Completed Work` / `Horas executadas`, o motor soma as horas reais e classifica Regular, Incompleto ou Excedente.

Há um arquivo de exemplo em `backend/samples/relatorio-contrato-exemplo.csv`.

## Como executar

### Docker Compose

```bash
docker compose up --build
```

- Interface: http://127.0.0.1:43123
- API: http://127.0.0.1:43124/api/health

### Sem Docker (desenvolvimento)

PostgreSQL local com banco `aderencia` e usuário `aderencia`.

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 43124

cd ../frontend
npm install
npm run dev
```

## Regras

- Segunda a sexta exigem lançamento; sábado, domingo, feriado e ponto facultativo não.
- Não exige lançamento antes da data de entrada, depois da saída ou em datas futuras.
- Carga diária padrão: 8h.
- Aderência do mês = soma de `min(executado, esperado)` / soma do esperado.

## Testes

```bash
cd backend
python3 -m pytest
```

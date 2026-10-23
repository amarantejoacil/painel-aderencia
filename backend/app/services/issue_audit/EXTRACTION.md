# Extração de comentários — Auditoria de Issues

## Issues (WIQL)

- `POST {base}/{coleção}/{projeto}/_apis/wit/wiql?api-version=7.1`
- Filtros: `TeamProject`, `WorkItemType`, `System.CreatedDate` ou `System.ChangedDate` (intervalo `[ano-01-01, ano+1-01-01)`).
- Uma resposta por consulta; sem `continuationToken`. Acima de ~20.000 IDs, a consulta é refeita mês a mês.

## Comentários (fonte em produção)

- `GET {base}/{coleção}/_apis/wit/workItems/{id}/updates?$top=200&$skip=…&api-version=7.1`
- Comentário = revisão com `fields.System.History.newValue` não vazio.
- Autor = `revisedBy` (`id`, `uniqueName`, `displayName`); data = `revisedDate`.
- Limite: 100 páginas × 200 revisões por Issue.

## API alternativa de comentários

- Escopo do projeto: `GET {base}/{coleção}/{projeto}/_apis/wit/workItems/{id}/comments?api-version=7.1-preview.4`.
- Escopo da coleção (sem projeto) costuma retornar 404 no Azure DevOps Server TJMT.
- A auditoria **CTI** continua usando apenas o histórico; a API de comentários do projeto pode ser usada na **validação** para diagnosticar divergências com `System.CommentCount`.

## Riscos conhecidos

- Histórico (`System.History`) ≠ contador de “comentários” da UI do Azure (`System.CommentCount`).
- Exemplo observado: Issue CTI #1667 — UI 35, histórico 34, API de comentários do projeto 35 (um comentário sem `System.History` na revisão).
- Edições geram nova revisão; exclusões não são detectadas.
- Menções no texto não definem autoria (somente `revisedBy`).
- WIQL truncado ou falha parcial deixa Issues fora do resultado armazenado.

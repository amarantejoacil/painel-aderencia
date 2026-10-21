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

- `GET …/workItems/{id}/comments?api-version=7.1-preview.4` (e outras preview).
- No Azure DevOps Server TJMT pode retornar 404; a validação sonda essa API por Issue na amostra.

## Riscos conhecidos

- Histórico (`System.History`) ≠ contador de “comentários” da UI do Azure.
- Edições geram nova revisão; exclusões não são detectadas.
- Menções no texto não definem autoria (somente `revisedBy`).
- WIQL truncado ou falha parcial deixa Issues fora do resultado armazenado.

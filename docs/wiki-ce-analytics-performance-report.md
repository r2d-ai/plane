# Wiki page/collection analytics — measured indexes (WIKI-09b)

Status: implementation evidence for the WIKI-09b PR. Spec: `docs/wiki-ce-spec.md`
§21. Plan: `docs/wiki-ce-implementation-plan.md` §12.3.

This report is generated from the opt-in suite in
`apps/api/plane/tests/perf/test_page_analytics_perf.py` and run inside the
repository-supported test stack (`docker-compose-test.yml`, PostgreSQL 15.7).
Plans are `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; execution ms is the plan's
`Execution Time`.

## What was measured

Dataset: 600,000 `page_views` across 200 Wiki pages over a 30-day span; 50
Collections of 4 pages each (a page belongs to at most one Collection). The
query window is the last day, which is the shape the analytics endpoints use for
their default and explicit windows. `ANALYZE page_views` runs after load.

| path | shipped ms | index chosen | no-index ms | candidate ws ms | decision |
| --- | --- | --- | --- | --- | --- |
| page timeline (`page_id` + `viewed_at` range, `GROUP BY` day) | 0.46 | `page_view_page_viewed_idx` | 0.79 | 1.39 | **keep** `page_view_page_viewed_idx` |
| page totals (`page_id` + `viewed_at` range aggregate) | 0.18 | `page_view_page_viewed_idx` | 0.54 | 1.06 | covered by `page_view_page_viewed_idx` |
| collection roll-up (`collection_id` + `viewed_at` range) | 0.41 | `page_view_coll_viewed_idx` | 2.44 | 1.34 | **keep** `page_view_coll_viewed_idx` |
| workspace-wide export (`workspace_id` + `viewed_at` range, ordered) | 71.05 | — (Seq Scan) | 90.78 | 14.04 | **reject** `page_view_ws_viewed_idx` |

- The page timeline and page-total queries are the ones the page analytics and
  CSV export endpoints issue; the planner selects
  `(page_id, viewed_at)` in every run and it is 1.7×–3× faster than the
  pre-existing `page_id` FK index.
- The Collection roll-up selects `(collection_id, viewed_at)` and is ~6× faster
  than the `collection_id` FK index.
- The candidate `(workspace_id, viewed_at)` index is fast on a workspace-wide
  ordered scan, but **no endpoint issues that query** — page and collection
  exports are always scoped by page/collection. It is not shipped: an index is
  added only when a shipped endpoint's measured plan selects it.

### Indexes shipped

```sql
CREATE INDEX "page_view_page_viewed_idx" ON "page_views" ("page_id", "viewed_at");
CREATE INDEX "page_view_coll_viewed_idx" ON "page_views" ("collection_id", "viewed_at");
```

Both are declared on `PageView.Meta.indexes` and shipped by migration
`0128_page_analytics_and_comment_moderation` (`AddIndex`, reversible;
`migrate` → `migrate db 0127` → `migrate` verified). No data is touched: the
migration adds two indexes plus the new tables/columns only.

## Reproducing

```bash
WIKI_PERF=1 WIKI_PERF_REPORT=/code/wiki-analytics-perf-report.md \
    docker compose -f docker-compose-test.yml run --rm api-tests \
    pytest plane/tests/perf/test_page_analytics_perf.py --create-db
```

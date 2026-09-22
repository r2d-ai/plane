# Wiki performance validation and measured indexes (WIKI-04b)

Status: implementation evidence for the WIKI-04b PR. Spec: `docs/wiki-ce-spec.md`
§21. Plan: `docs/wiki-ce-implementation-plan.md` §7.8, §16.

This report is generated from the opt-in suite in
`apps/api/plane/tests/perf/` and run inside the repository-supported test stack
(`docker-compose-test.yml`, PostgreSQL 15.7). Times are single-run wall clock for
the whole HTTP round-trip plus `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
execution times for the SQL that reads `pages`. Fixtures are described below; the
raw generated reports are reproducible with the commands in
[Reproducing](#reproducing).

## What was measured

Datasets (bulk-created, then `ANALYZE`):

| dataset | shape | rows |
| --- | --- | --- |
| 1k | 1,000 flat Wiki pages + 4,000 project-scope rows + 20 archived | 5,000 |
| 5k | 5,000 flat Wiki pages + 20,000 project-scope rows + 100 archived | 25,000 |
| deep | single 200-level parent chain | 200 |
| wide | one root + 2,000 direct children | 2,001 |

Project-scope (`is_global = false`) rows are included because a real workspace
shares the `pages` table between project pages and Wiki pages; without them the
Wiki predicate `is_global = true` is non-selective and the measurement lies.
A slice is archived so the **Archived** navigation section (WIKI-04a) is
measured against a selective predicate.

Hot paths (WIKI-04a/§7.8): first Wiki load, permission-filtered list, archived
list, tree expansion, search, page open.

## Result with the shipped index (`pages_wiki_scope_idx`)

`(workspace_id, is_global, archived_at)` is selected by the planner on the Wiki
list, archived-list and root-level tree paths; the remaining paths use their
existing FK indexes. Execution ms is the plan's `Execution Time`; wall ms
includes Python serialization.

| dataset | path | wall ms | queries | plan exec ms | index used |
| --- | --- | --- | --- | --- | --- |
| 1k | first wiki load | 3309.4 | 4 | 14.86 | `pages_wiki_scope_idx` |
| 1k | permission-filtered list | 412.8 | 4 | 26.82 | `pages_wiki_scope_idx` |
| 1k | archived list | 37.4 | 4 | 2.29 | `pages_wiki_scope_idx` |
| 1k | tree expansion (root level) | 797.7 | 4 | 34.52 | `pages_wiki_scope_idx` |
| 1k | search | 90.0 | 2 | 46.16 | `pages_workspace_id_*` |
| 1k | page open | 157.6 | 5 | 0.15 | `pages_pkey` |
| 5k | first wiki load | 2784.4 | 4 | 114.35 | `pages_wiki_scope_idx` |
| 5k | permission-filtered list | 2516.8 | 4 | 88.35 | `pages_wiki_scope_idx` |
| 5k | archived list | 121.9 | 4 | 5.10 | `pages_wiki_scope_idx` |
| 5k | tree expansion (root level) | 3194.1 | 4 | 76.23 | `pages_wiki_scope_idx` |
| 5k | search | 207.8 | 2 | 224.60 | `pages_workspace_id_*` |
| 5k | page open | 15.7 | 5 | 0.05 | `pages_pkey` |
| deep | first wiki load | 162.8 | 4 | 9.47 | `pages_wiki_scope_idx` |
| deep | tree expansion (parent) | 26.8 | 4 | 1.43 | `pages_parent_id_*` |
| deep | search | 21.9 | 2 | 5.75 | `pages_workspace_id_*` |
| deep | page open | 26.6 | 5 | 0.09 | `pages_pkey` |
| wide | first wiki load | 1533.9 | 4 | 63.61 | `pages_wiki_scope_idx` |
| wide | tree expansion (parent) | 1114.9 | 4 | 28.04 | `pages_parent_id_*` |
| wide | archived list | 26.8 | 3 | 1.05 | `pages_wiki_scope_idx` |
| wide | search | 27.1 | 2 | 18.68 | `pages_workspace_id_*` |
| wide | page open | 13.0 | 5 | 0.06 | `pages_pkey` |

No hot path performs a `Seq Scan` on `pages`. The 5k list plan (index access is
~7 ms of the 114 ms; the rest is the mandatory sort/aggregate over 5,000 rows
returned to the client):

```text
Unique  (rows=5000)
  Sort  (rows=5000)
    Aggregate  (rows=5000)
      Sort  (rows=5000)
        Nested Loop  (rows=5000)
          Nested Loop  (rows=5000)
            Index Scan [workspaces_slug_...]  (rows=1)
            Bitmap Heap Scan [pages]  (rows=5000)
              Bitmap Index Scan [pages_wiki_scope_idx]  (rows=5000)
          Index Scan [page_labels_page_id_...]  (rows=0)
```

## Candidate index evaluation (spec §21)

Each spec §21 candidate was created, measured against its hot path, then dropped
(see `test_wiki_index_candidates`). A candidate is kept only when the planner
**selects it** and measured execution improves. The shipped index is dropped at
the start of the run so the baseline is a true "before"; it is restored
afterwards. Baseline is the 5k workspace (25,000 `pages` rows). Numbers are
ranges over repeated runs because the planner sits near cost ties at this size.

| path | candidate | baseline ms | indexed ms | planner used | decision |
| --- | --- | --- | --- | --- | --- |
| archived list | `(workspace_id, is_global, archived_at)` | 25–26 | 6–7 | **every run** | **shipped** (`pages_wiki_scope_idx`, ~4×) |
| archived list | `(workspace_id, is_global, archived_at) WHERE archived_at IS NOT NULL` | 25–26 | 5.8–6.0 | every run | rejected — duplicate predicate of the shipped index, no material extra win |
| first wiki load | `(workspace_id, is_global, archived_at)` | 109–143 | 68–97 when selected | intermittent | shipped as the same index; opportunistic gain (see note) |
| first wiki load | `(workspace_id, is_global, deleted_at, archived_at)` | 109–143 | 104–118 | intermittent | rejected — never beats the shipped index |
| first wiki load | `(workspace_id, created_at DESC) WHERE is_global AND deleted_at IS NULL AND archived_at IS NULL` | 109–143 | 100–158 | intermittent | rejected — slower / no reliable win |
| tree expansion (wide) | `(workspace_id, is_global, parent_id, sort_order)` | 55–63 | 29–55 | intermittent | rejected — existing `pages_parent_id` FK index already serves the path |
| version history | `(page_id, last_saved_at DESC)` | 1.4 | 1.3–2.8 | **no** | rejected — `pages_pkey`/FK path already sub-2 ms |
| version history | `(page_id, created_at DESC)` | 1.4 | 1.2–2.2 | **no** | rejected — planner keeps the existing FK path |

Combined run (only the shipped index present):

| path | baseline ms | with `pages_wiki_scope_idx` | note |
| --- | --- | --- | --- |
| archived list (5k) | 25–26 | 5.9–6.0 | −76%, deterministic — the reason the index ships |
| first wiki load (5k) | 109–143 | 113–133 | planner sometimes keeps the pre-existing `pages_workspace_id` cost tie |

**Why this index and nothing else.** The Archived path is the durable,
deterministic win: the planner selects the index in every run and it is ~4×
faster. The default list also benefits when the planner chooses it, but at these
sizes it sits on a cost tie with the pre-existing workspace FK index and the
query is dominated by the sort/aggregate over every returned row, so the gain is
opportunistic rather than guaranteed. No other §21 candidate is selected
reliably or improves on its path, so none is shipped.

### Index shipped

```sql
CREATE INDEX "pages_wiki_scope_idx" ON "pages" ("workspace_id", "is_global", "archived_at");
```

- Migration: `apps/api/plane/db/migrations/0123_page_pages_wiki_scope_idx.py`
  (`AddIndex`, reversible; `migrate` → `migrate db 0122` → `migrate` verified).
- Declared on `Page.Meta.indexes` so the `--nomigrations` test stack and the
  production schema agree.
- Data is untouched: the migration adds one index only; project Page rows,
  `is_global` values and `Page.workspace` are unchanged.

## Rejected / deferred

- **No index for search at these scales.** The 5k search plan is ~224 ms, but the
  cost is the `OR project_membership` branch forcing a join and an ILIKE scan of
  the whole workspace; a `pg_trgm` expression index would need `UPPER(...)`
  expression indexes and the blocked join remains. Follow-up, not a measured
  index win here.
- **Flat list cost is not an index problem.** The 5k list serializes 5,000 pages
  (wall 2.8 s) with a per-row `is_favorite` `Exists`, an `ArrayAgg` over
  `page_labels` and a `DISTINCT`. Indexes cannot reduce the returned row count;
  pagination (or a branch-scoped fetch) is the real fix and belongs to a
  separate change.
- **Collections / shares candidates** (`(collection_id, sort_order)`,
  `(page_id, member_id)`) target WIKI-05 models that do not exist yet.

## Migration policy compliance (§16)

- One logical schema change (Wiki scoped-list index), reversible.
- No destructive operation; no `is_global` rewrite; project Page rows untouched.
- `python manage.py makemigrations --check` → no changes detected.
- `migrate` → `migrate db 0122` → `migrate` verified under
  `docker-compose-test.yml`.
- Indexes added only from the measured plans above; no speculative index.

## Reproducing

```bash
# Full measurement report (1k/5k/deep/wide, with plans).
# /code is the mounted apps/api checkout, so reports land next to the code.
WIKI_PERF=1 WIKI_PERF_REPORT=/code/wiki-perf.md \
  docker compose -f docker-compose-test.yml run --rm api-tests \
  pytest plane/tests/perf/test_wiki_perf.py -k report --create-db

# Candidate index A/B evaluation (spec §21):
WIKI_PERF=1 WIKI_PERF_INDEX_REPORT=/code/wiki-index-candidates.md \
  docker compose -f docker-compose-test.yml run --rm api-tests \
  pytest plane/tests/perf/test_wiki_perf.py -k candidates
```

Both suites are skipped unless `WIKI_PERF=1` is set, so the default test run is
unaffected.

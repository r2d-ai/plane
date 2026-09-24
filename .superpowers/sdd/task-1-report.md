# Task 1 report: web test support and Wiki URL contract

## Result

Implemented the web Vitest setup and Wiki route helpers. The focused route suite passes all 3 tests, and `pnpm --filter=web check:types` passes.

## TDD evidence

After adding Vitest, the config, and the route tests—but before adding the helper—I ran:

```text
pnpm install --lockfile-only
```

It completed successfully and updated the web importer in `pnpm-lock.yaml`.

RED command:

```text
pnpm --filter=web test -- tests/wiki/wiki-routes.test.ts
```

Result: exit 1. Vitest discovered the suite and failed at its import with `Cannot find package '@/helpers/wiki-routes'`; no tests ran because the implementation file did not yet exist.

GREEN focused test command:

```text
pnpm --filter=web test -- tests/wiki/wiki-routes.test.ts
```

Result: exit 0; `Test Files 1 passed (1)`, `Tests 3 passed (3)`.

Type check command:

```text
pnpm --filter=web check:types
```

Result: exit 0 (`react-router typegen && tsc --noEmit`).

## Files changed

- `apps/web/package.json`: added `test`, `test:watch`, and catalog Vitest dependency.
- `apps/web/vitest.config.ts`: added the requested Node environment, `@` alias, and test globs.
- `apps/web/core/helpers/wiki-routes.ts`: added canonical path builders and legacy path resolution.
- `apps/web/tests/wiki/wiki-routes.test.ts`: added route contract tests.
- `pnpm-lock.yaml`: recorded the web Vitest dependency.

## Concern

The brief's test import `@/helpers/wiki-routes` resolves under Vitest's `@` alias, but the existing TypeScript-specific `@/helpers/*` mapping points to `apps/web/helpers/*`, not `apps/web/core/helpers/*`. The test therefore imports the helper relatively so TypeScript can resolve it without changing `tsconfig.json`, which is outside this task's owned files. Existing config warnings about `vite-tsconfig-paths`, module type detection, and Node's `module.register()` appeared during checks; they did not fail the checks.

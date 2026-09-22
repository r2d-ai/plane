/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// The live app validates its environment at import time. Tests import modules
// that transitively load `@/env`, so seed the required values before any test
// module is evaluated. Existing values (e.g. from a local .env) win.
process.env.API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
process.env.LIVE_SERVER_SECRET_KEY = process.env.LIVE_SERVER_SECRET_KEY ?? "test-live-server-secret";

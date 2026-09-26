/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Per-user Workspace Dashboard preferences (spec §15).
 *
 * Identity is `(workspace, user)`: one user's metric, grouping, visualization,
 * filter or time-range choices must never reconfigure the dashboard for anyone
 * else (§15.2), and a workspace's preferences must not leak into another
 * workspace. §15.1 accepts `localStorage` as the P0 store — there is no
 * backend table here — but the payload shape is the one a server-side store
 * would use, so moving it later does not touch a card id or a query.
 *
 * A plain observable store rather than a MobX one: the whole thing is a
 * key/value bag with a subscribe callback, and `useSyncExternalStore` consumes
 * that without pulling the store into the app-wide MobX graph.
 */

import {
  WORKSPACE_DASHBOARD_CARDS,
  defaultCardPreference,
  reconcileCardPreference,
  type TCardPreference,
} from "@/components/dashboards/v3/card-registry";
import { DEFAULT_GLOBAL_SCOPE, type TWorkspaceDashboardGlobalScope } from "@/components/dashboards/v3/batch-composer";

/** §15.3 — bump when the stored shape changes; older payloads are discarded. */
export const DASHBOARD_PREFERENCES_SCHEMA_VERSION = 1;

const STORAGE_KEY_PREFIX = "plane-dashboard-preferences";

/** §15 — the persisted shape. `schema_version` gates forward compatibility. */
export interface TWorkspaceDashboardPreferences {
  schema_version: number;
  global: TWorkspaceDashboardGlobalScope;
  cards: Record<string, TCardPreference>;
}

export const dashboardPreferencesStorageKey = (workspaceId: string, userId: string): string =>
  `${STORAGE_KEY_PREFIX}:${workspaceId}:${userId}`;

export const defaultDashboardPreferences = (): TWorkspaceDashboardPreferences => ({
  schema_version: DASHBOARD_PREFERENCES_SCHEMA_VERSION,
  global: { ...DEFAULT_GLOBAL_SCOPE, filters: {}, projectIds: [] },
  cards: Object.fromEntries(WORKSPACE_DASHBOARD_CARDS.map((card) => [card.id, defaultCardPreference(card.id)])),
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];

const asStringList = (value: unknown): Record<string, string[]> => {
  if (!isRecord(value)) return {};
  const out: Record<string, string[]> = {};
  for (const [key, entry] of Object.entries(value)) {
    const list = asStringArray(entry);
    if (list.length > 0) out[key] = list;
  }
  return out;
};

const asString = (value: unknown): string | undefined => (typeof value === "string" ? value : undefined);

/**
 * §15.3 — unknown card ids are ignored and every surviving value is clamped by
 * its card definition, so a preference written by an older release can never
 * produce an invalid query.
 */
export function sanitizeDashboardPreferences(raw: unknown): TWorkspaceDashboardPreferences {
  const base = defaultDashboardPreferences();
  if (!isRecord(raw)) return base;
  if (raw.schema_version !== DASHBOARD_PREFERENCES_SCHEMA_VERSION) return base;

  const global = isRecord(raw.global) ? raw.global : {};
  const customRange = isRecord(global.customRange)
    ? {
        start: asString(global.customRange.start),
        end: asString(global.customRange.end),
      }
    : undefined;

  const sanitizedGlobal: TWorkspaceDashboardGlobalScope = {
    timePreset: (asString(global.timePreset) as TWorkspaceDashboardGlobalScope["timePreset"]) ?? base.global.timePreset,
    dateBasis: (asString(global.dateBasis) as TWorkspaceDashboardGlobalScope["dateBasis"]) ?? base.global.dateBasis,
    filters: asStringList(global.filters),
    projectIds: asStringArray(global.projectIds),
  };
  if (customRange?.start && customRange.end) {
    sanitizedGlobal.customRange = { start: customRange.start, end: customRange.end };
  }

  const storedCards = isRecord(raw.cards) ? raw.cards : {};
  const cards: Record<string, TCardPreference> = {};
  for (const definition of WORKSPACE_DASHBOARD_CARDS) {
    const stored = isRecord(storedCards[definition.id]) ? storedCards[definition.id] : {};
    cards[definition.id] = reconcileCardPreference(definition, stored as Partial<TCardPreference>);
  }

  return { schema_version: DASHBOARD_PREFERENCES_SCHEMA_VERSION, global: sanitizedGlobal, cards };
}

type Listener = () => void;

/** Minimal `localStorage` surface, injectable so tests need no DOM. */
export interface TDashboardPreferencesStorage {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

const defaultStorage = (): TDashboardPreferencesStorage | null => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    // Storage can be blocked entirely; preferences then live for the session.
    return null;
  }
};

export class DashboardPreferencesStore {
  private workspaceId: string | null = null;
  private userId: string | null = null;
  private storage: TDashboardPreferencesStorage | null;
  private state: TWorkspaceDashboardPreferences = defaultDashboardPreferences();
  private listeners = new Set<Listener>();

  constructor(storage: TDashboardPreferencesStorage | null = defaultStorage()) {
    this.storage = storage;
  }

  /**
   * Point the store at one `(workspace, user)` pair and load its payload.
   * Switching either half swaps the whole bag, which is what keeps two
   * workspaces — or two people on a shared browser — isolated.
   */
  setIdentity = (workspaceId: string | null, userId: string | null): void => {
    if (this.workspaceId === workspaceId && this.userId === userId) return;
    this.workspaceId = workspaceId;
    this.userId = userId;
    this.state = this.read(workspaceId, userId);
    this.emit();
  };

  getSnapshot = (): TWorkspaceDashboardPreferences => this.state;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getGlobalScope = (): TWorkspaceDashboardGlobalScope => this.state.global;

  getCardPreference = (cardId: string): TCardPreference => this.state.cards[cardId] ?? defaultCardPreference(cardId);

  /** A global change invalidates every card consistently (§20). */
  setGlobalScope = (updates: Partial<TWorkspaceDashboardGlobalScope>): void => {
    this.commit({
      ...this.state,
      global: { ...this.state.global, ...updates },
    });
  };

  /**
   * §20 — a card-local change touches only that card. The store holds one entry
   * per card id, so nothing else in the payload can move.
   */
  setCardPreference = (cardId: string, updates: Partial<TCardPreference>): void => {
    const definition = WORKSPACE_DASHBOARD_CARDS.find((card) => card.id === cardId);
    if (!definition) return;
    this.commit({
      ...this.state,
      cards: {
        ...this.state.cards,
        [cardId]: reconcileCardPreference(definition, { ...this.state.cards[cardId], ...updates }),
      },
    });
  };

  /** §8.4 — one card back to product defaults. */
  resetCard = (cardId: string): void => {
    const definition = WORKSPACE_DASHBOARD_CARDS.find((card) => card.id === cardId);
    if (!definition) return;
    this.commit({ ...this.state, cards: { ...this.state.cards, [cardId]: defaultCardPreference(cardId) } });
  };

  /** §8.4 — the whole preference bag back to product defaults. */
  reset = (): void => {
    this.commit(defaultDashboardPreferences());
  };

  private commit = (next: TWorkspaceDashboardPreferences): void => {
    this.state = next;
    this.persist();
    this.emit();
  };

  private read = (workspaceId: string | null, userId: string | null): TWorkspaceDashboardPreferences => {
    if (!workspaceId || !userId) return defaultDashboardPreferences();
    try {
      const stored = this.storage?.getItem(dashboardPreferencesStorageKey(workspaceId, userId));
      if (!stored) return defaultDashboardPreferences();
      return sanitizeDashboardPreferences(JSON.parse(stored));
    } catch {
      return defaultDashboardPreferences();
    }
  };

  private persist = (): void => {
    if (!this.workspaceId || !this.userId) return;
    try {
      this.storage?.setItem(dashboardPreferencesStorageKey(this.workspaceId, this.userId), JSON.stringify(this.state));
    } catch {
      // Quota or private-mode failure: the session keeps working in memory.
    }
  };

  private emit = (): void => {
    for (const listener of this.listeners) listener();
  };
}

/** App-wide instance. `setIdentity` is called by the dashboard shell on mount. */
export const dashboardPreferencesStore = new DashboardPreferencesStore();

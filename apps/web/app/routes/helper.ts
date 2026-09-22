/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RouteConfigEntry } from "@react-router/dev/routes";

/**
 * Find a route anywhere in the tree by file path.
 */
function findRouteByFile(
  routes: RouteConfigEntry[],
  fileKey: string,
  parent?: RouteConfigEntry
): { route: RouteConfigEntry; parent?: RouteConfigEntry } | undefined {
  for (const route of routes) {
    if (route.file === fileKey) return { route, parent };
    if (Array.isArray(route.children) && route.children.length > 0) {
      const nested = findRouteByFile(route.children, fileKey, route);
      if (nested) return nested;
    }
  }
  return undefined;
}

/**
 * Splice an extended entry's children into the matching core layout route
 * anywhere in the tree (top-level or nested). Returns a copy with the
 * matching layout's children extended.
 */
function attachExtendedChildrenToCoreRoute(core: RouteConfigEntry[], extended: RouteConfigEntry[]): RouteConfigEntry[] {
  return core.map((coreRoute) => {
    const baseChildren = Array.isArray(coreRoute.children) ? coreRoute.children : [];
    const matchingExtended = extended.find((extRoute) => extRoute.file === coreRoute.file);

    if (matchingExtended) {
      const extendedChildren = Array.isArray(matchingExtended.children) ? matchingExtended.children : [];
      return {
        ...coreRoute,
        children: extendedChildren.length > 0 ? mergeRoutes(baseChildren, extendedChildren) : baseChildren,
      };
    }

    // Recurse into nested children so nested core layouts get the matching
    // extended entries attached too.
    if (baseChildren.length > 0) {
      return {
        ...coreRoute,
        children: attachExtendedChildrenToCoreRoute(baseChildren, extended),
      };
    }

    return coreRoute;
  });
}

/**
 * Merges two route configurations intelligently.
 * - Deep merges children when the same layout file exists in both arrays
 * - Deduplicates routes by file property, preferring extended over core
 * - Maintains order: core routes first, then extended routes at each level
 * - When an extended layout file matches a NESTED core route, the extended
 *   children are attached to that nested core route instead of being emitted
 *   as a duplicate top-level route.
 */
export function mergeRoutes(core: RouteConfigEntry[], extended: RouteConfigEntry[]): RouteConfigEntry[] {
  // Step 0: collect extended entries that target a nested core layout.
  const nestedTargets = new Set<string>();
  for (const extRoute of extended) {
    const match = findRouteByFile(core, extRoute.file ?? "");
    if (match && match.parent) {
      nestedTargets.add(extRoute.file ?? "");
    }
  }

  // Step 1: Build the top-level route map from core first
  const routeMap = new Map<string, RouteConfigEntry>();
  for (const coreRoute of core) {
    const fileKey = coreRoute.file;
    if (fileKey) routeMap.set(fileKey, coreRoute);
  }

  // Step 2: Process extended routes that don't target a nested core layout
  for (const extendedRoute of extended) {
    const fileKey = extendedRoute.file ?? "";
    if (!fileKey) continue;
    if (nestedTargets.has(fileKey)) continue;

    if (routeMap.has(fileKey)) {
      const coreRoute = routeMap.get(fileKey)!;
      if (coreRoute.children && extendedRoute.children) {
        const mergedChildren = mergeRoutes(
          Array.isArray(coreRoute.children) ? coreRoute.children : [],
          Array.isArray(extendedRoute.children) ? extendedRoute.children : []
        );
        routeMap.set(fileKey, {
          ...extendedRoute,
          children: mergedChildren,
        });
      } else {
        routeMap.set(fileKey, extendedRoute);
      }
    } else {
      routeMap.set(fileKey, extendedRoute);
    }
  }

  // Step 3: Walk the (top-level) routeMap and splice any nested-target
  // extended children into their matching core layouts (recursively).
  const nestedOnlyExtended = extended.filter((extRoute) => nestedTargets.has(extRoute.file ?? ""));
  const updatedCore = attachExtendedChildrenToCoreRoute(Array.from(routeMap.values()), nestedOnlyExtended);

  // Step 4: Build final array maintaining order (core first, then extended-only)
  const result: RouteConfigEntry[] = [];
  for (const coreRoute of core) {
    const fileKey = coreRoute.file;
    if (fileKey && routeMap.has(fileKey)) {
      const matched = updatedCore.find((r) => r.file === fileKey);
      result.push(matched ?? routeMap.get(fileKey)!);
      routeMap.delete(fileKey);
    } else if (!fileKey) {
      result.push(coreRoute);
    }
  }

  for (const extendedRoute of extended) {
    const fileKey = extendedRoute.file ?? "";
    if (!fileKey) continue;
    if (nestedTargets.has(fileKey)) continue;
    if (routeMap.has(fileKey)) {
      result.push(routeMap.get(fileKey)!);
      routeMap.delete(fileKey);
    }
  }

  return result;
}

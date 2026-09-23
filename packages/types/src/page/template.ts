/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** A workspace-scoped Wiki page template (spec §16, backend PageTemplate). */
export type TPageTemplate = {
  id: string;
  workspace: string;
  name: string;
  description_stripped: string | null;
  logo_props: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

/** Payload for creating a template. */
export type TPageTemplateCreatePayload = {
  name: string;
  description_html?: string;
  logo_props?: Record<string, unknown> | null;
};

/** Payload for updating a template. */
export type TPageTemplateUpdatePayload = Partial<Pick<TPageTemplateCreatePayload, "name" | "logo_props">>;

/** Payload for instantiating a page from a template. */
export type TPageTemplateUsePayload = {
  name?: string;
  parent?: string | null;
  access?: number;
};

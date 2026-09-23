/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TPagePublish = {
  /** Publish row id; null while the page has never been published. */
  id: string | null;
  workspace: string | null;
  page: string;
  /** Public token. Null means the page is not currently published. */
  anchor: string | null;
  is_disabled?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type TPagePublishSettings = {
  anchor: string;
  publishLink: string;
};

/** Anonymous payload of a published Wiki page (space app). */
export type TPublishedPage = {
  anchor: string;
  name: string;
  description_html: string;
  updated_at: string;
};

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TPageCommentActorDetail = {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string;
};

export type TPageComment = {
  id: string;
  workspace: string;
  page: string;
  actor: string;
  actor_detail: TPageCommentActorDetail;
  comment_html: string;
  comment_json: Record<string, unknown>;
  comment_stripped: string | null;
  parent: string | null;
  edited_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

export type TPageCommentPayload = {
  comment_html: string;
  comment_json?: Record<string, unknown>;
  parent?: string | null;
};

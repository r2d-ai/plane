/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum EPageShareRole {
  VIEW = 5,
  COMMENT = 10,
  EDIT = 15,
}

export type TPageShareMemberDetail = {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string;
};

export type TPageShare = {
  id: string;
  workspace: string;
  page: string;
  member: string;
  member_detail: TPageShareMemberDetail;
  role: EPageShareRole;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

export type TPageSharePayload = {
  member: string;
  role: EPageShareRole;
};

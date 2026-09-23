/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TPageComment, TPageCommentPayload } from "@plane/types";
import { APIService } from "@/services/api.service";

export class PageCommentService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchAll(workspaceSlug: string, pageId: string): Promise<TPageComment[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/comments/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, pageId: string, data: TPageCommentPayload): Promise<TPageComment> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/comments/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    pageId: string,
    commentId: string,
    data: Partial<TPageCommentPayload>
  ): Promise<TPageComment> {
    return this.patch(`/api/workspaces/${workspaceSlug}/pages/${pageId}/comments/${commentId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async remove(workspaceSlug: string, pageId: string, commentId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/comments/${commentId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TPage,
  TPageTemplate,
  TPageTemplateCreatePayload,
  TPageTemplateUpdatePayload,
  TPageTemplateUsePayload,
} from "@plane/types";
import { APIService } from "@/services/api.service";

export class WorkspacePageTemplateService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchAll(workspaceSlug: string): Promise<TPageTemplate[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-templates/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchById(workspaceSlug: string, templateId: string): Promise<TPageTemplate> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-templates/${templateId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: TPageTemplateCreatePayload): Promise<TPageTemplate> {
    return this.post(`/api/workspaces/${workspaceSlug}/page-templates/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, templateId: string, data: TPageTemplateUpdatePayload): Promise<TPageTemplate> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-templates/${templateId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async remove(workspaceSlug: string, templateId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/page-templates/${templateId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Instantiate a new Wiki page from a template. */
  async use(workspaceSlug: string, templateId: string, data: TPageTemplateUsePayload): Promise<TPage> {
    return this.post(`/api/workspaces/${workspaceSlug}/page-templates/${templateId}/use/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Snapshot an existing Wiki page as a template. */
  async savePageAsTemplate(workspaceSlug: string, pageId: string, data: { name?: string }): Promise<TPageTemplate> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/save-as-template/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

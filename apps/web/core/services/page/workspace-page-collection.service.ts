/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TPageCollection,
  TPageCollectionCreatePayload,
  TPageCollectionUpdatePayload,
  TPageCollectionMember,
  TPageCollectionMemberPayload,
  TPageCollectionPage,
  TPageCollectionPageReorderPayload,
  TPageCollectionReorderPayload,
} from "@plane/types";
import { APIService } from "@/services/api.service";

export class WorkspacePageCollectionService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  // -- collection CRUD --------------------------------------------------

  async fetchAll(workspaceSlug: string): Promise<TPageCollection[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-collections/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchById(workspaceSlug: string, collectionId: string): Promise<TPageCollection> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: TPageCollectionCreatePayload): Promise<TPageCollection> {
    return this.post(`/api/workspaces/${workspaceSlug}/page-collections/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    collectionId: string,
    data: TPageCollectionUpdatePayload
  ): Promise<TPageCollection> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async remove(workspaceSlug: string, collectionId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async reorder(workspaceSlug: string, data: TPageCollectionReorderPayload): Promise<void> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-collections/reorder/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // -- members ----------------------------------------------------------

  async fetchMembers(workspaceSlug: string, collectionId: string): Promise<TPageCollectionMember[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/members/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async addMember(
    workspaceSlug: string,
    collectionId: string,
    data: TPageCollectionMemberPayload
  ): Promise<TPageCollectionMember> {
    return this.post(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/members/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateMember(
    workspaceSlug: string,
    collectionId: string,
    memberId: string,
    data: Pick<TPageCollectionMemberPayload, "role">
  ): Promise<TPageCollectionMember> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/members/${memberId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async removeMember(workspaceSlug: string, collectionId: string, memberId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/members/${memberId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // -- pages ------------------------------------------------------------

  async fetchPages(workspaceSlug: string, collectionId: string): Promise<TPageCollectionPage[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/pages/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async addPage(workspaceSlug: string, collectionId: string, pageId: string): Promise<TPageCollectionPage> {
    return this.post(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/pages/`, {
      page: pageId,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async movePage(workspaceSlug: string, collectionId: string, pageId: string): Promise<TPageCollectionPage> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/pages/${pageId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async removePage(workspaceSlug: string, collectionId: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/pages/${pageId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async reorderPages(
    workspaceSlug: string,
    collectionId: string,
    data: TPageCollectionPageReorderPayload
  ): Promise<void> {
    return this.patch(`/api/workspaces/${workspaceSlug}/page-collections/${collectionId}/pages/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { unset, set } from "lodash-es";
import { makeObservable, observable, runInAction, action, computed } from "mobx";
import { computedFn } from "mobx-utils";
import type {
  TPageCollection,
  TPageCollectionMember,
  TPageCollectionPage,
  TPageCollectionCreatePayload,
  TPageCollectionUpdatePayload,
  TPageCollectionMemberPayload,
} from "@plane/types";
import { WorkspacePageCollectionService } from "@/services/page";
import type { CoreRootStore } from "../root.store";

type TLoader = "init-loader" | "mutation-loader" | undefined;

export interface IPageCollectionStore {
  loader: TLoader;
  data: Record<string, TPageCollection>;
  members: Record<string, TPageCollectionMember[]>;
  collectionPages: Record<string, TPageCollectionPage[]>;
  isAnyCollectionAvailable: boolean;
  fetchCollections: (workspaceSlug: string) => Promise<TPageCollection[] | undefined>;
  fetchCollectionById: (workspaceSlug: string, collectionId: string) => Promise<TPageCollection | undefined>;
  createCollection: (workspaceSlug: string, data: TPageCollectionCreatePayload) => Promise<TPageCollection | undefined>;
  updateCollection: (
    workspaceSlug: string,
    collectionId: string,
    data: TPageCollectionUpdatePayload
  ) => Promise<TPageCollection | undefined>;
  removeCollection: (workspaceSlug: string, collectionId: string) => Promise<void>;
  reorderCollections: (workspaceSlug: string, collectionIds: string[], sortOrders: number[]) => Promise<void>;
  fetchMembers: (workspaceSlug: string, collectionId: string) => Promise<TPageCollectionMember[]>;
  addMember: (
    workspaceSlug: string,
    collectionId: string,
    data: TPageCollectionMemberPayload
  ) => Promise<TPageCollectionMember | undefined>;
  updateMemberRole: (
    workspaceSlug: string,
    collectionId: string,
    memberId: string,
    role: TPageCollectionMemberPayload["role"]
  ) => Promise<TPageCollectionMember | undefined>;
  removeMember: (workspaceSlug: string, collectionId: string, memberId: string) => Promise<void>;
  fetchCollectionPages: (workspaceSlug: string, collectionId: string) => Promise<TPageCollectionPage[]>;
  addPageToCollection: (
    workspaceSlug: string,
    collectionId: string,
    pageId: string
  ) => Promise<TPageCollectionPage | undefined>;
  movePageToCollection: (
    workspaceSlug: string,
    collectionId: string,
    pageId: string
  ) => Promise<TPageCollectionPage | undefined>;
  removePageFromCollection: (workspaceSlug: string, collectionId: string, pageId: string) => Promise<void>;
  reorderPages: (workspaceSlug: string, collectionId: string, pageIds: string[], sortOrders: number[]) => Promise<void>;
  getCollectionById: (collectionId: string) => TPageCollection | undefined;
  getMembersByCollectionId: (collectionId: string) => TPageCollectionMember[];
  getPagesByCollectionId: (collectionId: string) => TPageCollectionPage[];
}

export class PageCollectionStore implements IPageCollectionStore {
  loader: TLoader = "init-loader";
  data: Record<string, TPageCollection> = {};
  members: Record<string, TPageCollectionMember[]> = {};
  collectionPages: Record<string, TPageCollectionPage[]> = {};
  service: WorkspacePageCollectionService;
  rootStore: CoreRootStore;

  constructor(private store: CoreRootStore) {
    makeObservable(this, {
      loader: observable.ref,
      data: observable,
      members: observable,
      collectionPages: observable,
      isAnyCollectionAvailable: computed,
      fetchCollections: action,
      fetchCollectionById: action,
      createCollection: action,
      updateCollection: action,
      removeCollection: action,
      reorderCollections: action,
      fetchMembers: action,
      addMember: action,
      updateMemberRole: action,
      removeMember: action,
      fetchCollectionPages: action,
      addPageToCollection: action,
      movePageToCollection: action,
      removePageFromCollection: action,
      reorderPages: action,
    });
    this.rootStore = store;
    this.service = new WorkspacePageCollectionService();
  }

  get isAnyCollectionAvailable() {
    if (this.loader) return true;
    return Object.keys(this.data).length > 0;
  }

  getCollectionById = computedFn((collectionId: string) => this.data?.[collectionId] || undefined);

  getMembersByCollectionId = computedFn((collectionId: string) => this.members?.[collectionId] || []);

  getPagesByCollectionId = computedFn((collectionId: string) => this.collectionPages?.[collectionId] || []);

  fetchCollections = async (workspaceSlug: string) => {
    if (!workspaceSlug) return undefined;
    runInAction(() => {
      this.loader = Object.keys(this.data).length > 0 ? "mutation-loader" : "init-loader";
    });

    const collections = await this.service.fetchAll(workspaceSlug);
    runInAction(() => {
      const newMap: Record<string, TPageCollection> = {};
      for (const col of collections) {
        if (col?.id) newMap[col.id] = col;
      }
      this.data = newMap;
      this.loader = undefined;
    });
    return collections;
  };

  fetchCollectionById = async (workspaceSlug: string, collectionId: string) => {
    if (!workspaceSlug || !collectionId) return undefined;
    const collection = await this.service.fetchById(workspaceSlug, collectionId);
    runInAction(() => {
      if (collection?.id) set(this.data, [collection.id], collection);
    });
    return collection;
  };

  createCollection = async (workspaceSlug: string, data: TPageCollectionCreatePayload) => {
    if (!workspaceSlug) return undefined;
    runInAction(() => {
      this.loader = "mutation-loader";
    });

    const collection = await this.service.create(workspaceSlug, data);
    runInAction(() => {
      if (collection?.id) set(this.data, [collection.id], collection);
      this.loader = undefined;
    });
    return collection;
  };

  updateCollection = async (workspaceSlug: string, collectionId: string, data: TPageCollectionUpdatePayload) => {
    if (!workspaceSlug || !collectionId) return undefined;
    runInAction(() => {
      this.loader = "mutation-loader";
    });

    const collection = await this.service.update(workspaceSlug, collectionId, data);
    runInAction(() => {
      if (collection?.id) set(this.data, [collection.id], collection);
      this.loader = undefined;
    });
    return collection;
  };

  removeCollection = async (workspaceSlug: string, collectionId: string) => {
    if (!workspaceSlug || !collectionId) return;
    await this.service.remove(workspaceSlug, collectionId);
    runInAction(() => {
      unset(this.data, [collectionId]);
      unset(this.members, [collectionId]);
      unset(this.collectionPages, [collectionId]);
    });
  };

  reorderCollections = async (workspaceSlug: string, collectionIds: string[], sortOrders: number[]) => {
    if (!workspaceSlug || !collectionIds.length) return;
    const collections = collectionIds.map((id, index) => ({
      id,
      sort_order: sortOrders[index],
    }));

    // optimistic update
    runInAction(() => {
      for (const [idx, id] of collectionIds.entries()) {
        const col = this.data[id];
        if (col) col.sort_order = sortOrders[idx];
      }
    });

    await this.service.reorder(workspaceSlug, { collections });
  };

  fetchMembers = async (workspaceSlug: string, collectionId: string) => {
    if (!workspaceSlug || !collectionId) return [];
    const membersResult = await this.service.fetchMembers(workspaceSlug, collectionId);
    runInAction(() => {
      set(this.members, [collectionId], membersResult);
    });
    return membersResult;
  };

  addMember = async (workspaceSlug: string, collectionId: string, data: TPageCollectionMemberPayload) => {
    if (!workspaceSlug || !collectionId) return undefined;
    const member = await this.service.addMember(workspaceSlug, collectionId, data);
    runInAction(() => {
      const existing = this.members[collectionId] || [];
      const idx = existing.findIndex((m) => m.id === member.id);
      if (idx >= 0) existing[idx] = member;
      else set(this.members, [collectionId], [...existing, member]);
      const col = this.data[collectionId];
      if (col) col.member_count = (this.members[collectionId] || []).length;
    });
    return member;
  };

  updateMemberRole = async (
    workspaceSlug: string,
    collectionId: string,
    memberId: string,
    role: TPageCollectionMemberPayload["role"]
  ) => {
    if (!workspaceSlug || !collectionId || !memberId) return undefined;
    const member = await this.service.updateMember(workspaceSlug, collectionId, memberId, { role });
    runInAction(() => {
      const existing = this.members[collectionId] || [];
      const idx = existing.findIndex((m) => m.id === memberId);
      if (idx >= 0) existing[idx] = member;
    });
    return member;
  };

  removeMember = async (workspaceSlug: string, collectionId: string, memberId: string) => {
    if (!workspaceSlug || !collectionId || !memberId) return;
    await this.service.removeMember(workspaceSlug, collectionId, memberId);
    runInAction(() => {
      const existing = this.members[collectionId] || [];
      set(
        this.members,
        [collectionId],
        existing.filter((m) => m.id !== memberId)
      );
      const col = this.data[collectionId];
      if (col) col.member_count = (this.members[collectionId] || []).length;
    });
  };

  fetchCollectionPages = async (workspaceSlug: string, collectionId: string) => {
    if (!workspaceSlug || !collectionId) return [];
    const pages = await this.service.fetchPages(workspaceSlug, collectionId);
    runInAction(() => {
      set(this.collectionPages, [collectionId], pages);
    });
    return pages;
  };

  addPageToCollection = async (workspaceSlug: string, collectionId: string, pageId: string) => {
    if (!workspaceSlug || !collectionId || !pageId) return undefined;
    const association = await this.service.addPage(workspaceSlug, collectionId, pageId);
    runInAction(() => {
      const existing = this.collectionPages[collectionId] || [];
      set(this.collectionPages, [collectionId], [...existing, association]);
      const col = this.data[collectionId];
      if (col) col.page_count = (this.collectionPages[collectionId] || []).length;
    });
    return association;
  };

  movePageToCollection = async (workspaceSlug: string, collectionId: string, pageId: string) => {
    if (!workspaceSlug || !collectionId || !pageId) return undefined;
    const association = await this.service.movePage(workspaceSlug, collectionId, pageId);
    // Re-fetch pages for the collection since move can affect multiple pages
    await this.fetchCollectionPages(workspaceSlug, collectionId);
    return association;
  };

  removePageFromCollection = async (workspaceSlug: string, collectionId: string, pageId: string) => {
    if (!workspaceSlug || !collectionId || !pageId) return;
    await this.service.removePage(workspaceSlug, collectionId, pageId);
    runInAction(() => {
      const existing = this.collectionPages[collectionId] || [];
      set(
        this.collectionPages,
        [collectionId],
        existing.filter((p) => p.page !== pageId)
      );
      const col = this.data[collectionId];
      if (col) col.page_count = (this.collectionPages[collectionId] || []).length;
    });
  };

  reorderPages = async (workspaceSlug: string, collectionId: string, pageIds: string[], sortOrders: number[]) => {
    if (!workspaceSlug || !collectionId || !pageIds.length) return;
    const pages = pageIds.map((page, index) => ({
      page,
      sort_order: sortOrders[index],
    }));

    // optimistic update
    runInAction(() => {
      const existing = this.collectionPages[collectionId] || [];
      for (const [idx, pageId] of pageIds.entries()) {
        const assoc = existing.find((p) => p.page === pageId);
        if (assoc) assoc.sort_order = sortOrders[idx];
      }
    });

    await this.service.reorderPages(workspaceSlug, collectionId, { pages });
  };
}

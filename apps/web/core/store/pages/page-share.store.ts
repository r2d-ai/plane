/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction, action } from "mobx";
import type { TPageShare, TPageSharePayload, EPageShareRole } from "@plane/types";
import { WorkspacePageService } from "@/services/page";

const workspacePageService = new WorkspacePageService();

export interface IPageShareStore {
  shares: TPageShare[];
  loader: boolean;
  error: string | null;
  fetchShares: (workspaceSlug: string, pageId: string) => Promise<TPageShare[]>;
  addShare: (workspaceSlug: string, pageId: string, data: TPageSharePayload) => Promise<TPageShare | undefined>;
  updateShare: (
    workspaceSlug: string,
    pageId: string,
    shareId: string,
    role: EPageShareRole
  ) => Promise<TPageShare | undefined>;
  removeShare: (workspaceSlug: string, pageId: string, shareId: string) => Promise<void>;
  clearShares: () => void;
}

export class PageShareStore implements IPageShareStore {
  shares: TPageShare[] = [];
  loader: boolean = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      shares: observable,
      loader: observable.ref,
      error: observable.ref,
      fetchShares: action,
      addShare: action,
      updateShare: action,
      removeShare: action,
      clearShares: action,
    });
  }

  fetchShares = async (workspaceSlug: string, pageId: string): Promise<TPageShare[]> => {
    try {
      runInAction(() => {
        this.loader = true;
        this.error = null;
      });
      const shares = await workspacePageService.fetchShares(workspaceSlug, pageId);
      runInAction(() => {
        this.shares = shares;
        this.loader = false;
      });
      return shares;
    } catch (error) {
      runInAction(() => {
        this.loader = false;
        this.error = "Failed to fetch shares";
      });
      throw error;
    }
  };

  addShare = async (
    workspaceSlug: string,
    pageId: string,
    data: TPageSharePayload
  ): Promise<TPageShare | undefined> => {
    const share = await workspacePageService.addShare(workspaceSlug, pageId, data);
    runInAction(() => {
      this.shares.push(share);
    });
    return share;
  };

  updateShare = async (
    workspaceSlug: string,
    pageId: string,
    shareId: string,
    role: EPageShareRole
  ): Promise<TPageShare | undefined> => {
    const share = await workspacePageService.updateShare(workspaceSlug, pageId, shareId, { role });
    runInAction(() => {
      const index = this.shares.findIndex((s) => s.id === shareId);
      if (index !== -1) this.shares[index] = share;
    });
    return share;
  };

  removeShare = async (workspaceSlug: string, pageId: string, shareId: string): Promise<void> => {
    await workspacePageService.removeShare(workspaceSlug, pageId, shareId);
    runInAction(() => {
      this.shares = this.shares.filter((s) => s.id !== shareId);
    });
  };

  clearShares = () => {
    runInAction(() => {
      this.shares = [];
      this.error = null;
    });
  };
}

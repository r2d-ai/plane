/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction, action } from "mobx";
import type { TPagePublish } from "@plane/types";
import { WorkspacePageService } from "@/services/page";

const workspacePageService = new WorkspacePageService();

export interface IPagePublishStore {
  publishSettings: TPagePublish | null;
  loader: boolean;
  error: string | null;
  fetchPublish: (workspaceSlug: string, pageId: string) => Promise<TPagePublish>;
  publishPage: (workspaceSlug: string, pageId: string) => Promise<TPagePublish>;
  unPublishPage: (workspaceSlug: string, pageId: string, publishId: string) => Promise<void>;
}

export class PagePublishStore implements IPagePublishStore {
  publishSettings: TPagePublish | null = null;
  loader: boolean = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      publishSettings: observable.ref,
      loader: observable.ref,
      error: observable.ref,
      fetchPublish: action,
      publishPage: action,
      unPublishPage: action,
    });
  }

  fetchPublish = async (workspaceSlug: string, pageId: string): Promise<TPagePublish> => {
    try {
      runInAction(() => {
        this.loader = true;
        this.error = null;
      });
      const publishSettings = await workspacePageService.fetchPublish(workspaceSlug, pageId);
      runInAction(() => {
        this.publishSettings = publishSettings;
        this.loader = false;
      });
      return publishSettings;
    } catch (error) {
      runInAction(() => {
        this.loader = false;
        this.error = "Failed to fetch publish settings";
      });
      throw error;
    }
  };

  publishPage = async (workspaceSlug: string, pageId: string): Promise<TPagePublish> => {
    const publishSettings = await workspacePageService.publish(workspaceSlug, pageId);
    runInAction(() => {
      this.publishSettings = publishSettings;
    });
    return publishSettings;
  };

  unPublishPage = async (workspaceSlug: string, pageId: string, publishId: string): Promise<void> => {
    await workspacePageService.unPublish(workspaceSlug, pageId, publishId);
    runInAction(() => {
      this.publishSettings = { id: null, workspace: null, page: pageId, anchor: null };
    });
  };
}

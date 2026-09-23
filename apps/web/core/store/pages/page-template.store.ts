/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { unset, set } from "lodash-es";
import { makeObservable, observable, runInAction, action, computed } from "mobx";
import { computedFn } from "mobx-utils";
import type {
  TPage,
  TPageTemplate,
  TPageTemplateCreatePayload,
  TPageTemplateUpdatePayload,
  TPageTemplateUsePayload,
} from "@plane/types";
import { WorkspacePageTemplateService } from "@/services/page";
import type { CoreRootStore } from "../root.store";

type TLoader = "init-loader" | "mutation-loader" | undefined;

export interface IPageTemplateStore {
  loader: TLoader;
  data: Record<string, TPageTemplate>;
  isAnyTemplateAvailable: boolean;
  getTemplateById: (templateId: string) => TPageTemplate | undefined;
  fetchTemplates: (workspaceSlug: string) => Promise<TPageTemplate[] | undefined>;
  createTemplate: (workspaceSlug: string, data: TPageTemplateCreatePayload) => Promise<TPageTemplate | undefined>;
  updateTemplate: (
    workspaceSlug: string,
    templateId: string,
    data: TPageTemplateUpdatePayload
  ) => Promise<TPageTemplate | undefined>;
  removeTemplate: (workspaceSlug: string, templateId: string) => Promise<void>;
  useTemplate: (workspaceSlug: string, templateId: string, data: TPageTemplateUsePayload) => Promise<TPage | undefined>;
  savePageAsTemplate: (workspaceSlug: string, pageId: string, name: string) => Promise<TPageTemplate | undefined>;
}

export class PageTemplateStore implements IPageTemplateStore {
  loader: TLoader = "init-loader";
  data: Record<string, TPageTemplate> = {};
  service: WorkspacePageTemplateService;
  rootStore: CoreRootStore;

  constructor(private store: CoreRootStore) {
    makeObservable(this, {
      loader: observable.ref,
      data: observable,
      isAnyTemplateAvailable: computed,
      fetchTemplates: action,
      createTemplate: action,
      updateTemplate: action,
      removeTemplate: action,
      useTemplate: action,
      savePageAsTemplate: action,
    });
    this.rootStore = store;
    this.service = new WorkspacePageTemplateService();
  }

  get isAnyTemplateAvailable() {
    if (this.loader) return true;
    return Object.keys(this.data).length > 0;
  }

  getTemplateById = computedFn((templateId: string) => this.data?.[templateId] || undefined);

  fetchTemplates = async (workspaceSlug: string) => {
    if (!workspaceSlug) return undefined;
    runInAction(() => {
      this.loader = Object.keys(this.data).length > 0 ? "mutation-loader" : "init-loader";
    });
    try {
      const templates = await this.service.fetchAll(workspaceSlug);
      runInAction(() => {
        this.data = {};
        for (const template of templates) {
          if (template?.id) set(this.data, [template.id], template);
        }
        this.loader = undefined;
      });
      return templates;
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
      });
      throw error;
    }
  };

  createTemplate = async (workspaceSlug: string, data: TPageTemplateCreatePayload) => {
    if (!workspaceSlug) return undefined;
    const template = await this.service.create(workspaceSlug, data);
    runInAction(() => {
      if (template?.id) set(this.data, [template.id], template);
    });
    return template;
  };

  updateTemplate = async (workspaceSlug: string, templateId: string, data: TPageTemplateUpdatePayload) => {
    if (!workspaceSlug || !templateId) return undefined;
    const template = await this.service.update(workspaceSlug, templateId, data);
    runInAction(() => {
      if (template?.id) set(this.data, [template.id], template);
    });
    return template;
  };

  removeTemplate = async (workspaceSlug: string, templateId: string) => {
    if (!workspaceSlug || !templateId) return;
    await this.service.remove(workspaceSlug, templateId);
    runInAction(() => {
      unset(this.data, [templateId]);
    });
  };

  useTemplate = async (workspaceSlug: string, templateId: string, data: TPageTemplateUsePayload) => {
    if (!workspaceSlug || !templateId) return undefined;
    return this.service.use(workspaceSlug, templateId, data);
  };

  savePageAsTemplate = async (workspaceSlug: string, pageId: string, name: string) => {
    if (!workspaceSlug || !pageId) return undefined;
    const template = await this.service.savePageAsTemplate(workspaceSlug, pageId, { name });
    runInAction(() => {
      if (template?.id) set(this.data, [template.id], template);
    });
    return template;
  };
}

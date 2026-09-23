/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computed, makeObservable } from "mobx";
import { computedFn } from "mobx-utils";
// constants
import { EPageAccess, EUserPermissions } from "@plane/constants";
import type { TPage } from "@plane/types";
import { EUserWorkspaceRoles } from "@plane/types";
import { getWikiHomePath, getWikiPagePath } from "../../helpers/wiki-routes";
// plane web store
import type { RootStore } from "@/store/root.store";
// services
import { WorkspacePageService } from "@/services/page";
const workspacePageService = new WorkspacePageService();
// store
import { BasePage } from "./base-page";
import type { TPageInstance } from "./base-page";

export type TWorkspacePage = TPageInstance & {
  /** workspace slug the page was fetched from; every page mutation targets it */
  sourceWorkspaceSlug: string;
};

export class WorkspacePage extends BasePage implements TWorkspacePage {
  constructor(
    store: RootStore,
    page: TPage,
    readonly sourceWorkspaceSlug: string
  ) {
    // initialize base instance
    super(store, page, {
      update: async (payload) => {
        if (!page.id) throw new Error("Missing required fields.");
        return await workspacePageService.update(sourceWorkspaceSlug, page.id, payload);
      },
      updateDescription: async (document) => {
        if (!page.id) throw new Error("Missing required fields.");
        await workspacePageService.updateDescription(sourceWorkspaceSlug, page.id, document);
      },
      updateAccess: async (payload) => {
        if (!page.id) throw new Error("Missing required fields.");
        await workspacePageService.updateAccess(sourceWorkspaceSlug, page.id, payload);
      },
      lock: async () => {
        if (!page.id) throw new Error("Missing required fields.");
        await workspacePageService.lock(sourceWorkspaceSlug, page.id);
      },
      unlock: async () => {
        if (!page.id) throw new Error("Missing required fields.");
        await workspacePageService.unlock(sourceWorkspaceSlug, page.id);
      },
      archive: async () => {
        if (!page.id) throw new Error("Missing required fields.");
        return await workspacePageService.archive(sourceWorkspaceSlug, page.id);
      },
      restore: async () => {
        if (!page.id) throw new Error("Missing required fields.");
        await workspacePageService.restore(sourceWorkspaceSlug, page.id);
      },
      duplicate: async () => {
        if (!page.id) throw new Error("Missing required fields.");
        return await workspacePageService.duplicate(sourceWorkspaceSlug, page.id);
      },
    });
    makeObservable(this, {
      // computed
      canCurrentUserAccessPage: computed,
      canCurrentUserEditPage: computed,
      canCurrentUserDuplicatePage: computed,
      canCurrentUserLockPage: computed,
      canCurrentUserChangeAccess: computed,
      canCurrentUserArchivePage: computed,
      canCurrentUserDeletePage: computed,
      canCurrentUserFavoritePage: computed,
      canCurrentUserMovePage: computed,
      isContentEditable: computed,
    });
  }

  /**
   * @description inherited entity mutations (favorites) target the workspace
   * the page was fetched from, never the router's current scope
   */
  protected getSourceWorkspaceSlug(): string {
    return this.sourceWorkspaceSlug;
  }

  private getCurrentUserWorkspaceRole = computedFn((): EUserPermissions | undefined => {
    const workspaceRole = this.rootStore.user.permission.getWorkspaceRoleByWorkspaceSlug(this.sourceWorkspaceSlug);
    if (!workspaceRole) return;
    if (typeof workspaceRole === "number") return workspaceRole as EUserPermissions;
    if (workspaceRole === EUserWorkspaceRoles.ADMIN) return EUserPermissions.ADMIN;
    if (workspaceRole === EUserWorkspaceRoles.MEMBER) return EUserPermissions.MEMBER;
    if (workspaceRole === EUserWorkspaceRoles.GUEST) return EUserPermissions.GUEST;
    return undefined;
  });

  /**
   * @description returns true if the current logged in user can access the page
   */
  get canCurrentUserAccessPage() {
    const isPagePublic = this.access === EPageAccess.PUBLIC;
    return isPagePublic || this.isCurrentUserOwner;
  }

  /**
   * @description returns true if the current logged in user can edit the page
   */
  get canCurrentUserEditPage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    const isPagePublic = this.access === EPageAccess.PUBLIC;
    return (
      (isPagePublic && !!workspaceRole && workspaceRole >= EUserPermissions.MEMBER) ||
      (!isPagePublic && this.isCurrentUserOwner)
    );
  }

  /**
   * @description returns true if the current logged in user can create a duplicate the page
   */
  get canCurrentUserDuplicatePage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return !!workspaceRole && workspaceRole >= EUserPermissions.MEMBER;
  }

  /**
   * @description returns true if the current logged in user can lock the page
   */
  get canCurrentUserLockPage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return this.isCurrentUserOwner || workspaceRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can change the access of the page
   */
  get canCurrentUserChangeAccess() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return this.isCurrentUserOwner || workspaceRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can archive the page
   */
  get canCurrentUserArchivePage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return this.isCurrentUserOwner || workspaceRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can delete the page
   */
  get canCurrentUserDeletePage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return this.isCurrentUserOwner || workspaceRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the current logged in user can favorite the page
   */
  get canCurrentUserFavoritePage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return !!workspaceRole && workspaceRole >= EUserPermissions.MEMBER;
  }

  /**
   * @description returns true if the current logged in user can move the page
   */
  get canCurrentUserMovePage() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    return this.isCurrentUserOwner || workspaceRole === EUserPermissions.ADMIN;
  }

  /**
   * @description returns true if the page can be edited
   */
  get isContentEditable() {
    const workspaceRole = this.getCurrentUserWorkspaceRole();
    const isOwner = this.isCurrentUserOwner;
    const isPublic = this.access === EPageAccess.PUBLIC;
    const isArchived = this.archived_at;
    const isLocked = this.is_locked;

    return (
      !isArchived && !isLocked && (isOwner || (isPublic && !!workspaceRole && workspaceRole >= EUserPermissions.MEMBER))
    );
  }

  getRedirectionLink = computedFn(() =>
    this.id ? getWikiPagePath(this.sourceWorkspaceSlug, this.id) : getWikiHomePath(this.sourceWorkspaceSlug)
  );
}

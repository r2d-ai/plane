/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction, action } from "mobx";
import type { TPageComment, TPageCommentPayload } from "@plane/types";
import { PageCommentService } from "@/services/page";

const pageCommentService = new PageCommentService();

export interface IPageCommentStore {
  comments: TPageComment[];
  loader: boolean;
  error: string | null;
  fetchComments: (workspaceSlug: string, pageId: string) => Promise<TPageComment[]>;
  createComment: (
    workspaceSlug: string,
    pageId: string,
    data: TPageCommentPayload
  ) => Promise<TPageComment | undefined>;
  updateComment: (
    workspaceSlug: string,
    pageId: string,
    commentId: string,
    data: Partial<TPageCommentPayload>
  ) => Promise<TPageComment | undefined>;
  removeComment: (workspaceSlug: string, pageId: string, commentId: string) => Promise<void>;
  clearComments: () => void;
}

export class PageCommentStore implements IPageCommentStore {
  comments: TPageComment[] = [];
  loader: boolean = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      comments: observable,
      loader: observable.ref,
      error: observable.ref,
      fetchComments: action,
      createComment: action,
      updateComment: action,
      removeComment: action,
      clearComments: action,
    });
  }

  fetchComments = async (workspaceSlug: string, pageId: string): Promise<TPageComment[]> => {
    try {
      runInAction(() => {
        this.loader = true;
        this.error = null;
      });
      const comments = await pageCommentService.fetchAll(workspaceSlug, pageId);
      runInAction(() => {
        this.comments = comments;
        this.loader = false;
      });
      return comments;
    } catch (error) {
      runInAction(() => {
        this.loader = false;
        this.error = "Failed to fetch comments";
      });
      throw error;
    }
  };

  createComment = async (
    workspaceSlug: string,
    pageId: string,
    data: TPageCommentPayload
  ): Promise<TPageComment | undefined> => {
    const comment = await pageCommentService.create(workspaceSlug, pageId, data);
    runInAction(() => {
      this.comments.unshift(comment);
    });
    return comment;
  };

  updateComment = async (
    workspaceSlug: string,
    pageId: string,
    commentId: string,
    data: Partial<TPageCommentPayload>
  ): Promise<TPageComment | undefined> => {
    const comment = await pageCommentService.update(workspaceSlug, pageId, commentId, data);
    runInAction(() => {
      const index = this.comments.findIndex((c) => c.id === commentId);
      if (index !== -1) this.comments[index] = comment;
    });
    return comment;
  };

  removeComment = async (workspaceSlug: string, pageId: string, commentId: string): Promise<void> => {
    await pageCommentService.remove(workspaceSlug, pageId, commentId);
    runInAction(() => {
      this.comments = this.comments.filter((c) => c.id !== commentId);
    });
  };

  clearComments = () => {
    runInAction(() => {
      this.comments = [];
      this.error = null;
    });
  };
}

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { logger } from "@plane/logger";
import { AppError } from "@/lib/errors";
import { getPageService } from "@/services/page/handler";
import type { HocusPocusServerContext } from "@/types";
import { DebounceManager } from "./debounce";

/**
 * Statuses the Page API returns when the effective Page permission no longer
 * allows the write (revoked access, read-only role, locked page -> 400,
 * private/removed page -> 404). Title sync must never bypass these: the write
 * is rejected upstream, and we only log it as an authorization outcome rather
 * than a transport failure.
 */
const TITLE_WRITE_FORBIDDEN_STATUSES = new Set([400, 401, 403, 404]);

export const isTitleWriteForbidden = (error: AppError): boolean =>
  error.statusCode !== undefined && TITLE_WRITE_FORBIDDEN_STATUSES.has(error.statusCode);

/**
 * Manages title update operations for a single document
 * Handles debouncing, aborting, and force saving title updates
 */
export class TitleUpdateManager {
  private documentName: string;
  private context: HocusPocusServerContext;
  private debounceManager: DebounceManager;
  private lastTitle: string | null = null;

  /**
   * Create a new TitleUpdateManager instance
   */
  constructor(documentName: string, context: HocusPocusServerContext, wait: number = 5000) {
    this.documentName = documentName;
    this.context = context;

    // Set up debounce manager with logging
    this.debounceManager = new DebounceManager({
      wait,
      logPrefix: `TitleManager[${documentName.substring(0, 8)}]`,
    });
  }

  /**
   * Schedule a debounced title update
   */
  scheduleUpdate(title: string): void {
    // Store the latest title
    this.lastTitle = title;

    // Schedule the update with the debounce manager
    this.debounceManager.schedule(this.updateTitle.bind(this), title);
  }

  /**
   * Update the title - will be called by the debounce manager
   */
  private async updateTitle(title: string, signal?: AbortSignal): Promise<void> {
    const service = getPageService(this.context.documentType, this.context);
    if (!service.updatePageProperties) {
      logger.warn(`No updateTitle method found for document ${this.documentName}`);
      return;
    }

    try {
      await service.updatePageProperties(this.documentName, {
        data: { name: title },
        abortSignal: signal,
      });

      // Clear last title only if it matches what we just updated
      if (this.lastTitle === title) {
        this.lastTitle = null;
      }
    } catch (error) {
      const appError = new AppError(error, {
        context: { operation: "updateTitle", documentName: this.documentName },
      });
      // The Page API is the authority on whether this write is allowed (page
      // lock -> 400, revoked access -> 403, private/removed -> 404). Surface it
      // as an authorization outcome instead of retrying as a transient error.
      if (isTitleWriteForbidden(appError)) {
        logger.warn(
          `Title sync rejected for document ${this.documentName}: effective permission does not allow writes`
        );
        return;
      }
      logger.error("Error updating title", appError);
    }
  }

  /**
   * Force save the current title immediately
   */
  async forceSave(): Promise<void> {
    // Ensure we have the current title
    if (!this.lastTitle) {
      return;
    }

    // Use the debounce manager to flush the operation
    await this.debounceManager.flush(this.updateTitle.bind(this));
  }

  /**
   * Cancel any pending updates
   */
  cancel(): void {
    this.debounceManager.cancel();
    this.lastTitle = null;
  }
}

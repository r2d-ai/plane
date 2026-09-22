/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Database as HocuspocusDatabase } from "@hocuspocus/extension-database";
// plane imports
import {
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
} from "@plane/editor";
import type { TDocumentPayload } from "@plane/types";
import { logger } from "@plane/logger";
// lib
import { AppError } from "@/lib/errors";
// services
import { getPageService } from "@/services/page/handler";
// type
import type { FetchPayloadWithContext, StorePayloadWithContext } from "@/types";
import { ForceCloseReason, CloseCode } from "@/types/admin-commands";
import { broadcastError } from "@/utils/broadcast-error";
// force close utility
import { forceCloseDocumentAcrossServers } from "./force-close-handler";

/**
 * HTTP statuses the Page APIs return when the caller is no longer allowed to
 * touch the document (revoked membership, downgraded role, private page, page
 * moved/deleted, unauthenticated). Kept in one place so the store path can
 * distinguish an authorization failure from a transient one.
 */
const PERSISTENCE_FORBIDDEN_STATUSES = new Set([401, 403, 404]);

const isPersistenceForbidden = (error: AppError): boolean =>
  error.statusCode !== undefined && PERSISTENCE_FORBIDDEN_STATUSES.has(error.statusCode);

export const fetchDocument = async ({ context, documentName: pageId, instance }: FetchPayloadWithContext) => {
  try {
    const service = getPageService(context.documentType, context);
    // fetch details
    const response = (await service.fetchDescriptionBinary(pageId)) as Buffer;
    const binaryData = new Uint8Array(response);
    // if binary data is empty, convert HTML to binary data
    if (binaryData.byteLength === 0) {
      const pageDetails = await service.fetchDetails(pageId);
      const convertedBinaryData = getBinaryDataFromDocumentEditorHTMLString(
        pageDetails.description_html ?? "<p></p>",
        pageDetails.name
      );
      if (convertedBinaryData) {
        // save the converted binary data back to the database
        try {
          const { contentBinaryEncoded, contentHTML, contentJSON } = getAllDocumentFormatsFromDocumentEditorBinaryData(
            convertedBinaryData,
            true
          );
          const payload: TDocumentPayload = {
            description_binary: contentBinaryEncoded,
            description_html: contentHTML,
            description_json: contentJSON,
          };
          await service.updateDescriptionBinary(pageId, payload);
        } catch (e) {
          const error = new AppError(e);
          logger.error("Failed to save binary after first conversion from html:", error);
        }
        return convertedBinaryData;
      }
    }
    // return binary data
    return binaryData;
  } catch (error) {
    const appError = new AppError(error, { context: { pageId } });
    logger.error("Error in fetching document", appError);

    // Broadcast error to frontend for user document types
    await broadcastError(instance, pageId, "Unable to load the page. Please try refreshing.", "fetch", context);

    throw appError;
  }
};

export const storeDocument = async ({
  context,
  state: pageBinaryData,
  documentName: pageId,
  instance,
}: StorePayloadWithContext) => {
  try {
    const service = getPageService(context.documentType, context);
    // convert binary data to all formats
    const { contentBinaryEncoded, contentHTML, contentJSON } = getAllDocumentFormatsFromDocumentEditorBinaryData(
      pageBinaryData,
      true
    );
    // create payload
    const payload: TDocumentPayload = {
      description_binary: contentBinaryEncoded,
      description_html: contentHTML,
      description_json: contentJSON,
    };
    await service.updateDescriptionBinary(pageId, payload);
  } catch (error) {
    const appError = new AppError(error, { context: { pageId } });
    logger.error("Error in updating document:", appError);

    // Check error types
    const isContentTooLarge = appError.statusCode === 413;

    // Workspace pages (Workspace Wiki / Company Wiki) must not keep a live
    // session alive once persistence is forbidden: access revoked, role
    // downgraded, page made private or removed. The Page API already rejects
    // the write, so no unauthorized bytes are stored; here we additionally
    // surface the failure and force the session closed. Project pages keep
    // their existing store behavior (regression guard).
    const isPersistenceDenied = context.documentType === "workspace_page" && isPersistenceForbidden(appError);

    // Determine if we should disconnect and unload
    const shouldDisconnect = isContentTooLarge || isPersistenceDenied;

    // Determine error message and code
    let errorMessage: string;
    let errorCode: "content_too_large" | "page_locked" | "page_archived" | undefined;

    if (isContentTooLarge) {
      errorMessage = "Document is too large to save. Please reduce the content size.";
      errorCode = "content_too_large";
    } else if (isPersistenceDenied) {
      errorMessage = "You no longer have permission to edit this page. Live editing has been stopped.";
    } else {
      errorMessage = "Unable to save the page. Please try again.";
    }

    // Broadcast error to frontend for user document types
    await broadcastError(instance, pageId, errorMessage, "store", context, errorCode, shouldDisconnect);

    // If we should disconnect, close connections and unload document
    if (shouldDisconnect) {
      // Map error code to ForceCloseReason with proper types
      const reason = isContentTooLarge ? ForceCloseReason.DOCUMENT_TOO_LARGE : ForceCloseReason.SECURITY_VIOLATION;

      const closeCode = isContentTooLarge ? CloseCode.DOCUMENT_TOO_LARGE : CloseCode.SECURITY_VIOLATION;

      // force close connections and unload document
      await forceCloseDocumentAcrossServers(instance, pageId, reason, closeCode);

      // Don't throw after force close - document is already unloaded
      // Throwing would cause hocuspocus's finally block to access the null document
      return;
    }

    throw appError;
  }
};

export class Database extends HocuspocusDatabase {
  constructor() {
    super({ fetch: fetchDocument, store: storeDocument });
  }
}

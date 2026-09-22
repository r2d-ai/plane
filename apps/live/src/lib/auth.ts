/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { IncomingHttpHeaders } from "http";
import type { TUserDetails } from "@plane/editor";
import { logger } from "@plane/logger";
import { AppError } from "@/lib/errors";
// services
import { UserService } from "@/services/user.service";
// types
import type { HocusPocusServerContext, TDocumentTypes } from "@/types";

/**
 * Authenticate the user
 * @param requestHeaders - The request headers
 * @param context - The context
 * @param token - The token
 * @returns The authenticated user
 */
export const onAuthenticate = async ({
  requestHeaders,
  requestParameters,
  context,
  token,
}: {
  requestHeaders: IncomingHttpHeaders;
  context: HocusPocusServerContext;
  requestParameters: URLSearchParams;
  token: string;
}) => {
  let cookie: string | undefined = undefined;
  let userId: string | undefined = undefined;

  // Extract cookie (fallback to request headers) and userId from token (for scenarios where
  // the cookies are not passed in the request headers)
  try {
    const parsedToken = JSON.parse(token) as TUserDetails;
    userId = parsedToken.id;
    cookie = parsedToken.cookie;
  } catch (error) {
    const appError = new AppError(error, {
      context: { operation: "onAuthenticate" },
    });
    logger.error("Token parsing failed, using request headers", appError);
  } finally {
    // If cookie is still not found, fallback to request headers
    if (!cookie) {
      cookie = requestHeaders.cookie?.toString();
    }
  }

  if (!cookie || !userId) {
    const appError = new AppError("Credentials not provided", { code: "AUTH_MISSING_CREDENTIALS" });
    logger.error("Credentials not provided", appError);
    throw appError;
  }

  // set cookie in context, so it can be used throughout the ws connection
  context.cookie = cookie ?? requestParameters.get("cookie") ?? "";
  context.documentType = requestParameters.get("documentType")?.toString() as TDocumentTypes;
  context.projectId = requestParameters.get("projectId");
  context.userId = userId;
  context.workspaceSlug = requestParameters.get("workspaceSlug");

  // Reject malformed connection parameters before any document bytes are touched.
  // This is defense in depth: the Page APIs the live service calls are themselves
  // permission-protected, so authorization is never decided here.
  validateDocumentConnection({
    documentType: context.documentType,
    workspaceSlug: context.workspaceSlug,
    projectId: context.projectId,
  });

  return await handleAuthentication({
    cookie: context.cookie,
    userId: context.userId,
  });
};

/**
 * Validate the document connection parameters.
 *
 * `project_page` requires a workspace slug and a project id; `workspace_page`
 * (Workspace Wiki / Company Wiki) requires a workspace slug and treats
 * `projectId` as optional (spec §5.4). Every other document type is rejected so
 * an unknown type can never be routed to a permissive service.
 */
export const validateDocumentConnection = ({
  documentType,
  workspaceSlug,
  projectId,
}: {
  documentType: TDocumentTypes;
  workspaceSlug: string | null | undefined;
  projectId: string | null | undefined;
}) => {
  if (documentType !== "project_page" && documentType !== "workspace_page") {
    throw new AppError(`Invalid document type ${documentType} provided.`, {
      code: "AUTH_INVALID_DOCUMENT_TYPE",
    });
  }

  if (!workspaceSlug) {
    throw new AppError("Workspace slug is required.", { code: "AUTH_MISSING_WORKSPACE_SLUG" });
  }

  if (documentType === "project_page" && !projectId) {
    throw new AppError("Project ID is required for project pages.", { code: "AUTH_MISSING_PROJECT_ID" });
  }
};

export const handleAuthentication = async ({ cookie, userId }: { cookie: string; userId: string }) => {
  // fetch current user info
  try {
    const userService = new UserService();
    const user = await userService.currentUser(cookie);
    if (user.id !== userId) {
      throw new AppError("Authentication unsuccessful: User ID mismatch", { code: "AUTH_USER_MISMATCH" });
    }

    return {
      user: {
        id: user.id,
        name: user.display_name,
      },
    };
  } catch (error) {
    const appError = new AppError(error, {
      context: { operation: "handleAuthentication" },
    });
    logger.error("Authentication failed", appError);
    throw new AppError("Authentication unsuccessful", { code: appError.code });
  }
};

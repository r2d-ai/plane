/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useCallback, useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { SPACE_BASE_PATH, SPACE_BASE_URL } from "@plane/constants";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { copyTextToClipboard } from "@plane/utils";
import { PagePublishStore } from "@/store/pages/page-publish.store";

type TPublishDialogProps = {
  isOpen: boolean;
  onClose: () => void;
  pageId: string;
};

export const PagePublishDialog = observer(function PagePublishDialog(props: TPublishDialogProps) {
  const { isOpen, onClose, pageId } = props;
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString() || "";

  const [publishStore] = useState(() => new PagePublishStore());
  const [isPublishing, setIsPublishing] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);

  useEffect(() => {
    if (isOpen && workspaceSlug && pageId) {
      publishStore.fetchPublish(workspaceSlug, pageId);
    }
  }, [isOpen, workspaceSlug, pageId, publishStore]);

  const publishSettings = publishStore.publishSettings;
  const isPublished = !!publishSettings?.anchor;
  const spaceAppUrl = (SPACE_BASE_URL.trim() === "" ? window.location.origin : SPACE_BASE_URL) + SPACE_BASE_PATH;
  const publishLink = isPublished ? `${spaceAppUrl}/p/${publishSettings?.anchor}` : "";

  const handlePublish = useCallback(async () => {
    if (!workspaceSlug || !pageId) return;
    setIsPublishing(true);
    try {
      await publishStore.publishPage(workspaceSlug, pageId);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Page published",
        message: "Anyone with the link can now view this page.",
      });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Failed to publish the page." });
    } finally {
      setIsPublishing(false);
    }
  }, [workspaceSlug, pageId, publishStore]);

  const handleRevoke = useCallback(async () => {
    if (!workspaceSlug || !pageId || !publishSettings?.id) return;
    setIsRevoking(true);
    try {
      await publishStore.unPublishPage(workspaceSlug, pageId, publishSettings.id);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Publication revoked",
        message: "The public link no longer works.",
      });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Failed to revoke the publication." });
    } finally {
      setIsRevoking(false);
    }
  }, [workspaceSlug, pageId, publishSettings?.id, publishStore]);

  const handleCopyLink = useCallback(() => {
    if (!publishLink) return;
    copyTextToClipboard(publishLink).then(() =>
      setToast({ type: TOAST_TYPE.SUCCESS, title: "", message: "Public page link copied successfully." })
    );
  }, [publishLink]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
        aria-label="Close publish dialog"
      />
      <div className="shadow-xl relative z-10 flex w-full max-w-lg flex-col gap-4 rounded-lg border border-subtle bg-layer-2 p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Publish Page</h3>
          <button onClick={onClose} className="text-tertiary hover:text-primary">
            &times;
          </button>
        </div>

        {publishStore.loader && <p className="text-xs text-tertiary">Loading...</p>}

        {!publishStore.loader && !isPublished && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-secondary">
              Publishing creates a public link anyone can open. Only this page is published — its child pages stay
              private.
            </p>
            <button
              onClick={handlePublish}
              disabled={isPublishing}
              className="bg-primary text-sm self-start rounded px-3 py-2 text-white disabled:opacity-60"
            >
              {isPublishing ? "Publishing..." : "Publish"}
            </button>
          </div>
        )}

        {!publishStore.loader && isPublished && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between rounded-md border border-subtle px-3 py-2">
              <a
                href={publishLink}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm truncate text-accent-primary underline"
              >
                {publishLink}
              </a>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyLink}
                className="text-xs rounded border border-subtle px-3 py-1.5 hover:bg-layer-1"
              >
                Copy link
              </button>
              <a
                href={publishLink}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs rounded border border-subtle px-3 py-1.5 hover:bg-layer-1"
              >
                Preview
              </a>
              <button
                onClick={handleRevoke}
                disabled={isRevoking}
                className="text-xs text-red-500 hover:text-red-700 rounded border border-subtle px-3 py-1.5 disabled:opacity-60"
              >
                {isRevoking ? "Revoking..." : "Revoke"}
              </button>
            </div>
            <p className="text-xs text-tertiary">Anyone with the link can view this page.</p>
          </div>
        )}
      </div>
    </div>
  );
});

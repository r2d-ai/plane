/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useCallback, useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { EPageShareRole } from "@plane/types";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { PageShareStore } from "@/store/pages/page-share.store";

type TShareDialogProps = {
  isOpen: boolean;
  onClose: () => void;
  pageId: string;
};

const PAGE_SHARE_ROLE_OPTIONS = [
  { value: EPageShareRole.VIEW, label: "View" },
  { value: EPageShareRole.COMMENT, label: "Comment" },
  { value: EPageShareRole.EDIT, label: "Edit" },
];

export const PageShareDialog = observer(function PageShareDialog(props: TShareDialogProps) {
  const { isOpen, onClose, pageId } = props;
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString() || "";

  const [shareStore] = useState(() => new PageShareStore());

  useEffect(() => {
    if (isOpen && workspaceSlug && pageId) {
      shareStore.fetchShares(workspaceSlug, pageId);
    }
  }, [isOpen, workspaceSlug, pageId, shareStore]);

  const handleRemoveShare = useCallback(
    async (shareId: string) => {
      if (!workspaceSlug || !pageId) return;
      try {
        await shareStore.removeShare(workspaceSlug, pageId, shareId);
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Share removed",
          message: "Page access has been removed.",
        });
      } catch {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error",
          message: "Failed to remove share.",
        });
      }
    },
    [workspaceSlug, pageId, shareStore]
  );

  const handleRoleChange = useCallback(
    async (shareId: string, role: EPageShareRole) => {
      if (!workspaceSlug || !pageId) return;
      try {
        await shareStore.updateShare(workspaceSlug, pageId, shareId, role);
      } catch {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error",
          message: "Failed to update role.",
        });
      }
    },
    [workspaceSlug, pageId, shareStore]
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
        aria-label="Close share dialog"
      />
      <div className="shadow-xl relative z-10 flex w-full max-w-lg flex-col gap-4 rounded-lg border border-subtle bg-layer-2 p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Share Page</h3>
          <button onClick={onClose} className="text-tertiary hover:text-primary">
            &times;
          </button>
        </div>

        {/* Current shares */}
        <div className="flex flex-col gap-2">
          <h4 className="text-sm font-medium text-secondary">Current access</h4>
          {shareStore.loader && <p className="text-xs text-tertiary">Loading...</p>}
          {!shareStore.loader && shareStore.shares.length === 0 && (
            <p className="text-xs text-tertiary">No members have been shared yet.</p>
          )}
          {shareStore.shares.map((share) => (
            <div key={share.id} className="flex items-center justify-between rounded-md border border-subtle px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-sm">{share.member_detail?.display_name || share.member_detail?.email}</span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={share.role}
                  onChange={(e) => handleRoleChange(share.id, Number(e.target.value) as EPageShareRole)}
                  className="text-xs rounded border border-subtle bg-layer-2 px-2 py-1"
                >
                  {PAGE_SHARE_ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <button onClick={() => handleRemoveShare(share.id)} className="text-xs text-red-500 hover:text-red-700">
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-tertiary">
          To share with a new member, use the page access controls or contact your workspace admin.
        </p>
      </div>
    </div>
  );
});

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
import { observer } from "mobx-react";
import { Trash2 } from "lucide-react";
import useSWR from "swr";
import { EPageCollectionRole, type TPageCollectionMember } from "@plane/types";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Button, ModalCore, EModalPosition, EModalWidth } from "@plane/ui";
import { usePageCollectionStore } from "@/hooks/store";

const ROLE_OPTIONS: { value: EPageCollectionRole; label: string }[] = [
  { value: EPageCollectionRole.VIEW, label: "View" },
  { value: EPageCollectionRole.COMMENT, label: "Comment" },
  { value: EPageCollectionRole.EDIT, label: "Edit" },
];

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  collectionId: string;
  collectionName: string;
};

export const CollectionMembersModal = observer(function CollectionMembersModal(props: Props) {
  const { isOpen, onClose, workspaceSlug, collectionId, collectionName } = props;
  const { t } = useTranslation();
  const collectionStore = usePageCollectionStore();

  const { data: members } = useSWR(
    isOpen && workspaceSlug && collectionId ? `COLLECTION_MEMBERS_${collectionId}` : null,
    () => collectionStore.fetchMembers(workspaceSlug, collectionId)
  );

  const handleUpdateRole = useCallback(
    async (memberId: string, role: EPageCollectionRole) => {
      try {
        await collectionStore.updateMemberRole(workspaceSlug, collectionId, memberId, role);
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: t("common.success"),
          message: t("wiki.collections.member_updated"),
        });
      } catch {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("common.error"),
          message: t("wiki.collections.member_update_failed"),
        });
      }
    },
    [collectionStore, workspaceSlug, collectionId, t]
  );

  const handleRemoveMember = useCallback(
    async (memberId: string) => {
      try {
        await collectionStore.removeMember(workspaceSlug, collectionId, memberId);
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: t("common.success"),
          message: t("wiki.collections.member_removed"),
        });
      } catch {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("common.error"),
          message: t("wiki.collections.member_remove_failed"),
        });
      }
    },
    [collectionStore, workspaceSlug, collectionId, t]
  );

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.LG}>
      <div className="space-y-4 p-5">
        <h3 className="text-18 font-medium text-secondary">
          {t("wiki.collections.manage_members")} — {collectionName}
        </h3>

        <p className="text-13 text-tertiary">
          {t("wiki.collections.no_members")} Use the API or invite workflow to add members.
        </p>

        {/* Current members list */}
        <div className="space-y-1">
          {members && members.length > 0 ? (
            members.map((member: TPageCollectionMember) => (
              <div key={member.id} className="flex items-center gap-3 rounded-md border border-subtle px-3 py-2">
                <div className="bg-custom-primary text-xs flex h-8 w-8 items-center justify-center rounded-full font-medium text-white">
                  {member.member_detail?.display_name?.charAt(0)?.toUpperCase() || "?"}
                </div>
                <div className="flex-1 truncate">
                  <p className="text-13 font-medium">{member.member_detail?.display_name}</p>
                  <p className="text-11 text-tertiary">{member.member_detail?.email}</p>
                </div>
                <select
                  value={member.role}
                  onChange={(e) => handleUpdateRole(member.member, Number(e.target.value) as EPageCollectionRole)}
                  className="rounded border border-subtle bg-transparent px-2 py-1 text-12 text-secondary"
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleRemoveMember(member.id)}
                  className="rounded p-1 text-tertiary transition-colors hover:bg-layer-1 hover:text-danger-primary"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          ) : (
            <p className="py-4 text-center text-13 text-tertiary">{t("wiki.collections.no_members")}</p>
          )}
        </div>

        <div className="flex justify-end border-t border-subtle pt-4">
          <Button variant="outline-primary" size="lg" onClick={onClose}>
            {t("common.done")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
});

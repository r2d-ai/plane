/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Check, Folder } from "lucide-react";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Button, ModalCore, EModalPosition, EModalWidth } from "@plane/ui";
import { cn } from "@plane/utils";
import { usePageCollectionStore } from "@/hooks/store";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  pageId: string;
  currentPageCollectionId?: string;
  onMoved?: () => Promise<void> | void;
};

export const MovePageToCollectionModal = observer(function MovePageToCollectionModal(props: Props) {
  const { isOpen, onClose, workspaceSlug, pageId, currentPageCollectionId, onMoved } = props;
  const { t } = useTranslation();
  const collectionStore = usePageCollectionStore();
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(currentPageCollectionId ?? null);
  const [isMoving, setIsMoving] = useState(false);

  const { data: collections } = useSWR(isOpen && workspaceSlug ? `WORKSPACE_COLLECTIONS_${workspaceSlug}` : null, () =>
    collectionStore.fetchCollections(workspaceSlug)
  );

  const { data: detectedCollectionId } = useSWR(
    isOpen && collections ? `PAGE_COLLECTION_MEMBERSHIP_${workspaceSlug}_${pageId}` : null,
    async () => {
      const memberships = await Promise.all(
        (collections ?? []).map(async (collection) => ({
          collectionId: collection.id,
          pages: await collectionStore.fetchCollectionPages(workspaceSlug, collection.id),
        }))
      );
      return memberships.find(({ pages }) => pages.some((item) => item.page === pageId))?.collectionId ?? null;
    }
  );

  const effectiveCurrentCollectionId = currentPageCollectionId ?? detectedCollectionId ?? undefined;

  useEffect(() => {
    if (!isOpen) return;
    setSelectedCollectionId(effectiveCurrentCollectionId ?? null);
  }, [isOpen, effectiveCurrentCollectionId]);

  const handleMove = useCallback(async () => {
    if (!selectedCollectionId) return;
    setIsMoving(true);
    try {
      await collectionStore.movePageToCollection(workspaceSlug, selectedCollectionId, pageId);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("common.success"),
        message: t("wiki.collections.page_moved"),
      });
      await onMoved?.();
      onClose();
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error"),
        message: t("wiki.collections.page_move_failed"),
      });
    } finally {
      setIsMoving(false);
    }
  }, [collectionStore, workspaceSlug, selectedCollectionId, pageId, t, onClose, onMoved]);

  const handleRemoveFromCollection = useCallback(async () => {
    if (!effectiveCurrentCollectionId) return;
    setIsMoving(true);
    try {
      await collectionStore.removePageFromCollection(workspaceSlug, effectiveCurrentCollectionId, pageId);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("common.success"),
        message: t("wiki.collections.page_removed_from_collection"),
      });
      setSelectedCollectionId(null);
      await onMoved?.();
      onClose();
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error"),
        message: t("wiki.collections.page_remove_failed"),
      });
    } finally {
      setIsMoving(false);
    }
  }, [collectionStore, workspaceSlug, effectiveCurrentCollectionId, pageId, t, onClose, onMoved]);

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.LG}>
      <div className="space-y-4 p-5">
        <h3 className="text-18 font-medium text-secondary">{t("wiki.collections.move_page_to_collection")}</h3>

        <div className="max-h-60 space-y-1 overflow-y-auto">
          {collections && collections.length > 0 ? (
            collections.map((collection) => (
              <button
                key={collection.id}
                type="button"
                onClick={() => setSelectedCollectionId(collection.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-13 transition-colors",
                  selectedCollectionId === collection.id
                    ? "border-accent-primary bg-accent-primary/5"
                    : "border-subtle hover:bg-layer-1"
                )}
              >
                <Folder className="h-4 w-4 flex-shrink-0 text-tertiary" />
                <div className="flex-1 truncate">
                  <span className="font-medium">{collection.name}</span>
                  <span className="ml-2 text-tertiary">
                    {collection.page_count} {t("wiki.collections.pages")}
                  </span>
                </div>
                {selectedCollectionId === collection.id && (
                  <Check className="h-4 w-4 flex-shrink-0 text-accent-primary" />
                )}
              </button>
            ))
          ) : (
            <p className="py-4 text-center text-13 text-tertiary">{t("wiki.collections.no_collections")}</p>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-subtle pt-4">
          <div>
            {effectiveCurrentCollectionId && (
              <Button variant="danger" size="lg" onClick={handleRemoveFromCollection} loading={isMoving}>
                {t("wiki.collections.remove_from_collection")}
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline-primary" size="lg" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="primary"
              size="lg"
              onClick={handleMove}
              loading={isMoving}
              disabled={!selectedCollectionId || selectedCollectionId === effectiveCurrentCollectionId}
            >
              {t("wiki_collections.add_existing_page_modal.submit")}
            </Button>
          </div>
        </div>
      </div>
    </ModalCore>
  );
});

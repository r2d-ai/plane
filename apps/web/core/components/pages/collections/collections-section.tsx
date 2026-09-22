/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useRef, useState } from "react";
import { observer } from "mobx-react";
import {
  ChevronDown,
  ChevronRight,
  Globe,
  GripVertical,
  Lock,
  MoreHorizontal,
  Pencil,
  Plus,
  Settings,
  Trash2,
} from "lucide-react";
import useSWR from "swr";
import { EPageCollectionAccess, type TPageCollection } from "@plane/types";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
import { usePageCollectionStore } from "@/hooks/store";
import { CollectionCreateEditModal } from "./collection-create-edit-modal";
import { CollectionDeleteModal } from "./collection-delete-modal";
import { CollectionMembersModal } from "./collection-members-modal";
import { CollectionPageTree } from "./collection-page-tree";

type TCollection = TPageCollection;

type CollectionRowProps = {
  collection: TCollection;
  workspaceSlug: string;
  canManage: boolean;
  isCompanyWiki?: boolean;
  expandedIds: Set<string>;
  toggleExpanded: (id: string) => void;
  onEdit: (collection: TPageCollection) => void;
  onDelete: (collection: TPageCollection) => void;
  onManageMembers: (collection: TPageCollection) => void;
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  canCreatePage?: boolean;
};

const CollectionRow = observer(function CollectionRow(props: CollectionRowProps) {
  const {
    collection,
    workspaceSlug,
    canManage,
    isCompanyWiki,
    expandedIds,
    toggleExpanded,
    onEdit,
    onDelete,
    onManageMembers,
    buildPageHref,
    canCreatePage,
  } = props;
  const { t } = useTranslation();
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const isExpanded = expandedIds.has(collection.id);

  const handleToggle = useCallback(() => toggleExpanded(collection.id), [collection.id, toggleExpanded]);

  // Drag/drop for reorder
  const canDrag = canManage && !collection.is_default;

  return (
    <div className="flex flex-col" data-collection-id={collection.id}>
      <div
        ref={rowRef}
        className={cn(
          "group/col-row flex h-8 cursor-pointer items-center gap-1 rounded-sm px-1 text-13 transition-colors hover:bg-layer-1",
          {
            "border-t-2 border-accent-strong": dropPosition === "before",
            "border-b-2 border-accent-strong": dropPosition === "after",
          }
        )}
      >
        {canDrag && (
          <span className="cursor-grab text-tertiary opacity-0 group-hover/col-row:opacity-100">
            <GripVertical className="h-3.5 w-3.5" />
          </span>
        )}
        <button
          type="button"
          onClick={handleToggle}
          className="grid size-4 place-items-center rounded-sm text-tertiary transition-colors hover:bg-layer-2 hover:text-primary"
        >
          {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        </button>
        <span className="flex flex-1 items-center gap-2 truncate">
          {collection.access === EPageCollectionAccess.PUBLIC ? (
            <Globe className="h-3.5 w-3.5 flex-shrink-0 text-tertiary" />
          ) : (
            <Lock className="h-3.5 w-3.5 flex-shrink-0 text-tertiary" />
          )}
          <span className="truncate font-medium">{collection.name}</span>
          {collection.is_default && (
            <span className="bg-custom-primary flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-white">
              {t("wiki.collections.default")}
            </span>
          )}
          <span className="flex-shrink-0 text-11 text-tertiary">{collection.page_count}</span>
        </span>
        {canManage && !isCompanyWiki && (
          <div className="relative">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="grid size-5 place-items-center rounded-sm text-tertiary opacity-0 transition-opacity group-hover/col-row:opacity-100 hover:bg-layer-2 hover:text-primary"
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </button>
            {showMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  role="presentation"
                  onClick={() => setShowMenu(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setShowMenu(false);
                  }}
                />
                <div className="shadow-lg absolute top-6 right-0 z-20 w-44 rounded-md border border-subtle bg-layer-2 py-1">
                  <button
                    type="button"
                    onClick={() => {
                      setShowMenu(false);
                      onManageMembers(collection);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-13 transition-colors hover:bg-layer-1"
                  >
                    <Settings className="h-3.5 w-3.5" />
                    {t("wiki.collections.manage_members")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowMenu(false);
                      onEdit(collection);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-13 transition-colors hover:bg-layer-1"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    {t("common.edit")}
                  </button>
                  {!collection.is_default && (
                    <button
                      type="button"
                      onClick={() => {
                        setShowMenu(false);
                        onDelete(collection);
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-13 text-danger-primary transition-colors hover:bg-layer-1"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {t("common.delete")}
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
      {isExpanded && (
        <div className="ml-4 border-l border-subtle pl-2">
          <CollectionPageTree
            workspaceSlug={workspaceSlug}
            collectionId={collection.id}
            buildPageHref={buildPageHref}
            canCreatePage={canManage && canCreatePage}
          />
        </div>
      )}
    </div>
  );
});

type TProps = {
  workspaceSlug: string;
  isCompanyWiki?: boolean;
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  canCreatePage?: boolean;
};

export const CollectionsSection = observer(function CollectionsSection(props: TProps) {
  const { workspaceSlug, isCompanyWiki, buildPageHref, canCreatePage } = props;
  const { t } = useTranslation();
  const collectionStore = usePageCollectionStore();
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editCollection, setEditCollection] = useState<TPageCollection | null>(null);
  const [deleteCollection, setDeleteCollection] = useState<TPageCollection | null>(null);
  const [membersCollection, setMembersCollection] = useState<TPageCollection | null>(null);

  const { data: collections } = useSWR(workspaceSlug ? `WORKSPACE_COLLECTIONS_${workspaceSlug}` : null, () =>
    collectionStore.fetchCollections(workspaceSlug)
  );

  const toggleExpanded = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleCreate = useCallback(
    async (data: { name: string; description: string; access: number }) => {
      await collectionStore.createCollection(workspaceSlug, data);
    },
    [collectionStore, workspaceSlug]
  );

  const handleUpdate = useCallback(
    async (data: { name: string; description: string; access: number }) => {
      if (!editCollection) return;
      await collectionStore.updateCollection(workspaceSlug, editCollection.id, data);
      setEditCollection(null);
    },
    [collectionStore, workspaceSlug, editCollection]
  );

  const handleDelete = useCallback(async () => {
    if (!deleteCollection) return;
    await collectionStore.removeCollection(workspaceSlug, deleteCollection.id);
    setDeleteCollection(null);
  }, [collectionStore, workspaceSlug, deleteCollection]);

  if (!collections || collections.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between px-1">
        <h4 className="tracking-wider text-11 font-semibold text-tertiary uppercase">
          {t("wiki.collections.section_title")}
        </h4>
        {canCreatePage && !isCompanyWiki && (
          <button
            type="button"
            onClick={() => setCreateModalOpen(true)}
            className="grid size-4 place-items-center rounded-sm text-tertiary transition-colors hover:bg-layer-1 hover:text-primary"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="flex flex-col gap-0.5" data-testid="collections-section">
        {collections
          .toSorted((a, b) => a.sort_order - b.sort_order)
          .map((collection) => (
            <CollectionRow
              key={collection.id}
              collection={collection}
              workspaceSlug={workspaceSlug}
              canManage={!isCompanyWiki}
              isCompanyWiki={isCompanyWiki}
              expandedIds={expandedIds}
              toggleExpanded={toggleExpanded}
              onEdit={setEditCollection}
              onDelete={setDeleteCollection}
              onManageMembers={setMembersCollection}
              buildPageHref={buildPageHref}
              canCreatePage={canCreatePage}
            />
          ))}
      </div>

      {/* Modals */}
      <CollectionCreateEditModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={handleCreate}
      />
      <CollectionCreateEditModal
        isOpen={!!editCollection}
        onClose={() => setEditCollection(null)}
        data={editCollection ?? undefined}
        onSubmit={handleUpdate}
      />
      {deleteCollection && (
        <CollectionDeleteModal
          isOpen={!!deleteCollection}
          onClose={() => setDeleteCollection(null)}
          onSubmit={handleDelete}
          title={deleteCollection.name}
        />
      )}
      {membersCollection && (
        <CollectionMembersModal
          isOpen={!!membersCollection}
          onClose={() => setMembersCollection(null)}
          workspaceSlug={workspaceSlug}
          collectionId={membersCollection.id}
          collectionName={membersCollection.name}
        />
      )}
    </div>
  );
});

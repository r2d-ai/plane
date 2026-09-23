/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useRouter } from "next/navigation";
import { FileText, Pencil, Trash2 } from "lucide-react";
// constants
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageTemplate } from "@plane/types";
import { AlertModalCore, Button, EModalPosition, EModalWidth, Input, ModalCore } from "@plane/ui";
// hooks
import { usePageTemplateStore } from "@/hooks/store";
import { useUser, useUserPermissions } from "@/hooks/store/user";

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  /** Builds the redirect URL after a page is created from a template. */
  buildPageHref: (params: { workspaceSlug: string; pageId: string }) => string;
  /** Optional parent the new page is nested under. */
  parentId?: string | null;
  /** Whether the current user may create pages in this workspace. */
  canCreatePage?: boolean;
};

export const PageTemplatesModal = observer(function PageTemplatesModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, buildPageHref, parentId = null, canCreatePage = true } = props;
  // i18n
  const { t } = useTranslation();
  // router
  const router = useRouter();
  // store hooks
  const { data, loader, fetchTemplates, useTemplate, removeTemplate, updateTemplate } = usePageTemplateStore();
  const { getWorkspaceRoleByWorkspaceSlug } = useUserPermissions();
  const { data: currentUser } = useUser();
  // states
  const [searchQuery, setSearchQuery] = useState("");
  const [usingId, setUsingId] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<TPageTemplate | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<TPageTemplate | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  const workspaceRole = workspaceSlug ? getWorkspaceRoleByWorkspaceSlug(workspaceSlug) : undefined;
  const isAdmin = workspaceRole === EUserPermissions.ADMIN;

  const templates = useMemo(() => {
    const list = Object.values(data ?? {});
    const query = searchQuery.trim().toLowerCase();
    if (!query) return list;
    return list.filter((template) => template.name.toLowerCase().includes(query));
  }, [data, searchQuery]);

  useEffect(() => {
    if (isOpen && workspaceSlug) void fetchTemplates(workspaceSlug);
  }, [isOpen, workspaceSlug, fetchTemplates]);

  useEffect(() => {
    if (!isOpen) {
      setSearchQuery("");
      setUsingId(null);
    }
  }, [isOpen]);

  const canManage = (template: TPageTemplate) => isAdmin || template.created_by === currentUser?.id;

  const handleUse = async (template: TPageTemplate) => {
    setUsingId(template.id);
    try {
      const page = await useTemplate(workspaceSlug, template.id, { parent: parentId });
      if (page?.id) {
        onClose();
        router.push(buildPageHref({ workspaceSlug, pageId: page.id }));
      }
    } catch (err: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error"),
        message: err?.error || t("wiki.templates.toasts.use_error"),
      });
    } finally {
      setUsingId(null);
    }
  };

  const handleRename = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!renameTarget || !renameValue.trim() || isMutating) return;
    setIsMutating(true);
    try {
      await updateTemplate(workspaceSlug, renameTarget.id, { name: renameValue.trim() });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("common.success"), message: t("wiki.templates.toasts.renamed") });
      setRenameTarget(null);
    } catch (err: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error"),
        message: err?.error || t("wiki.templates.toasts.rename_error"),
      });
    } finally {
      setIsMutating(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget || isMutating) return;
    setIsMutating(true);
    try {
      await removeTemplate(workspaceSlug, deleteTarget.id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("common.success"), message: t("wiki.templates.toasts.deleted") });
      setDeleteTarget(null);
    } catch (err: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("common.error"),
        message: err?.error || t("wiki.templates.toasts.delete_error"),
      });
    } finally {
      setIsMutating(false);
    }
  };

  return (
    <>
      <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.XL}>
        <div className="flex flex-col gap-4 p-5">
          <div>
            <h3 className="text-18 font-medium text-secondary">{t("wiki.templates.modal.title")}</h3>
            <p className="text-13 text-tertiary">{t("wiki.templates.modal.description")}</p>
          </div>

          <Input
            type="text"
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
            placeholder={t("wiki.templates.search_placeholder")}
            className="w-full text-14"
          />

          <div className="flex max-h-[420px] flex-col gap-1 overflow-y-auto">
            {loader && templates.length === 0 && (
              <p className="py-6 text-center text-13 text-tertiary">{t("common.loading")}</p>
            )}
            {!loader && templates.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-10">
                <FileText className="h-6 w-6 text-tertiary" />
                <p className="text-13 text-tertiary">{t("wiki.templates.empty")}</p>
              </div>
            )}
            {templates.map((template) => (
              <div
                key={template.id}
                className="group/template flex items-center gap-3 rounded-sm border border-subtle px-3 py-2 hover:bg-layer-1"
              >
                <FileText className="h-4 w-4 flex-shrink-0 text-tertiary" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-13 font-medium text-primary">{template.name}</span>
                  {template.description_stripped && (
                    <span className="truncate text-11 text-tertiary">{template.description_stripped}</span>
                  )}
                </div>
                {canManage(template) && (
                  <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover/template:opacity-100">
                    <button
                      type="button"
                      className="grid size-6 place-items-center rounded-sm text-tertiary hover:bg-layer-2 hover:text-primary"
                      onClick={() => {
                        setRenameTarget(template);
                        setRenameValue(template.name);
                      }}
                      aria-label={t("common.edit")}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      className="grid size-6 place-items-center rounded-sm text-tertiary hover:bg-layer-2 hover:text-danger-primary"
                      onClick={() => setDeleteTarget(template)}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
                {canCreatePage && (
                  <Button
                    variant="outline-primary"
                    size="sm"
                    onClick={() => handleUse(template)}
                    loading={usingId === template.id}
                  >
                    {t("wiki.templates.use")}
                  </Button>
                )}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-end border-t border-subtle pt-4">
            <Button variant="outline-primary" size="lg" onClick={onClose} type="button">
              {t("common.close")}
            </Button>
          </div>
        </div>
      </ModalCore>

      <ModalCore
        isOpen={!!renameTarget}
        handleClose={() => setRenameTarget(null)}
        position={EModalPosition.TOP}
        width={EModalWidth.LG}
      >
        <form onSubmit={handleRename} className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">{t("wiki.templates.rename_modal.title")}</h3>
          <Input
            type="text"
            value={renameValue}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRenameValue(e.target.value)}
            className="w-full text-14"
            maxLength={255}
          />
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline-primary" size="lg" type="button" onClick={() => setRenameTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button variant="primary" size="lg" type="submit" loading={isMutating} disabled={!renameValue.trim()}>
              {t("common.save_changes")}
            </Button>
          </div>
        </form>
      </ModalCore>

      <AlertModalCore
        isOpen={!!deleteTarget}
        handleClose={() => setDeleteTarget(null)}
        title={t("wiki.templates.delete_modal.title")}
        content={
          <p className="text-14 text-secondary">
            {t("wiki.templates.delete_modal.description", { name: deleteTarget?.name ?? "" })}
          </p>
        }
        primaryButtonText={{ default: t("common.delete"), loading: t("common.deleting") }}
        secondaryButtonText={t("common.cancel")}
        isSubmitting={isMutating}
        handleSubmit={handleDelete}
      />
    </>
  );
});

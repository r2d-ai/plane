/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FormEvent } from "react";
import { useState } from "react";
import { observer } from "mobx-react";
import { Globe, Lock } from "lucide-react";
import { EPageCollectionAccess, type TPageCollection } from "@plane/types";
import { useTranslation } from "@plane/i18n";
import { Button, Input, TextArea } from "@plane/ui";
import { cn } from "@plane/utils";

type Props = {
  data?: TPageCollection;
  onSubmit: (data: { name: string; description: string; access: EPageCollectionAccess }) => Promise<void>;
  onClose: () => void;
};

export const CollectionForm = observer(function CollectionForm(props: Props) {
  const { data, onSubmit, onClose } = props;
  const { t } = useTranslation();
  const [name, setName] = useState(data?.name ?? "");
  const [description, setDescription] = useState(data?.description ?? "");
  const [access, setAccess] = useState<EPageCollectionAccess>(data?.access ?? EPageCollectionAccess.PUBLIC);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!data;
  const isNameEmpty = !name.trim();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isNameEmpty || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onSubmit({ name: name.trim(), description: description.trim(), access });
      onClose();
    } catch (err: any) {
      setError(err?.error || err?.detail || t("common.error_message"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-5">
      <h3 className="text-18 font-medium text-secondary">
        {isEdit ? t("wiki.collections.edit_collection") : t("wiki.collections.create_collection")}
      </h3>

      <div className="space-y-1">
        <label className="text-13 font-medium text-secondary" htmlFor="collection-name">
          {t("common.name")}
        </label>
        <Input
          id="collection-name"
          type="text"
          value={name}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
          placeholder={t("wiki.collections.name_placeholder")}
          className="w-full text-14"
          required
          maxLength={255}
        />
      </div>

      <div className="space-y-1">
        <label className="text-13 font-medium text-secondary" htmlFor="collection-description">
          {t("common.description")}
        </label>
        <TextArea
          id="collection-description"
          value={description}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
          placeholder={t("wiki.collections.description_placeholder")}
          className="w-full resize-none text-14"
          rows={3}
        />
      </div>

      <div className="space-y-1">
        <label className="text-13 font-medium text-secondary">{t("common.access.label")}</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setAccess(EPageCollectionAccess.PUBLIC)}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-13 transition-colors",
              access === EPageCollectionAccess.PUBLIC
                ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
                : "border-subtle text-tertiary hover:border-strong"
            )}
          >
            <Globe className="h-3.5 w-3.5" />
            {t("common.access.public")}
          </button>
          <button
            type="button"
            onClick={() => setAccess(EPageCollectionAccess.PRIVATE)}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-13 transition-colors",
              access === EPageCollectionAccess.PRIVATE
                ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
                : "border-subtle text-tertiary hover:border-strong"
            )}
          >
            <Lock className="h-3.5 w-3.5" />
            {t("common.access.private")}
          </button>
        </div>
      </div>

      {error && <p className="text-12 text-danger-primary">{error}</p>}

      <div className="flex items-center justify-end gap-2 border-t border-subtle pt-4">
        <Button variant="outline-primary" size="lg" onClick={onClose} type="button">
          {t("common.cancel")}
        </Button>
        <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={isNameEmpty || isSubmitting}>
          {isSubmitting
            ? t("common.loading")
            : isEdit
              ? t("common.save_changes")
              : t("wiki.collections.create_collection")}
        </Button>
      </div>
    </form>
  );
});

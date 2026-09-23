/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
// ui
import { Button, EModalPosition, EModalWidth, Input, ModalCore } from "@plane/ui";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  defaultName: string;
  onSubmit: (name: string) => Promise<void>;
};

export const SaveAsTemplateModal = observer(function SaveAsTemplateModal(props: Props) {
  const { isOpen, onClose, defaultName, onSubmit } = props;
  // i18n
  const { t } = useTranslation();
  // states
  const [name, setName] = useState(defaultName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setName(defaultName);
      setError(null);
    }
  }, [isOpen, defaultName]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim() || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onSubmit(name.trim());
      onClose();
    } catch (err: any) {
      setError(err?.error || err?.detail || t("common.something_went_wrong"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.LG}>
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <h3 className="text-18 font-medium text-secondary">{t("wiki.templates.save_modal.title")}</h3>
        <p className="text-13 text-tertiary">{t("wiki.templates.save_modal.description")}</p>
        <div className="space-y-1">
          <label className="text-13 font-medium text-secondary" htmlFor="template-name">
            {t("common.name")}
          </label>
          <Input
            id="template-name"
            type="text"
            value={name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
            placeholder={t("wiki.templates.name_placeholder")}
            className="w-full text-14"
            maxLength={255}
          />
          {error && <p className="text-12 text-danger-primary">{error}</p>}
        </div>
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline-primary" size="lg" onClick={onClose} type="button">
            {t("common.cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={!name.trim()}>
            {isSubmitting ? t("common.saving") : t("wiki.templates.save_modal.submit")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { AlertModalCore } from "@plane/ui";
import { useTranslation } from "@plane/i18n";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => Promise<void>;
  title: string;
};

export const CollectionDeleteModal = observer(function CollectionDeleteModal(props: Props) {
  const { isOpen, onClose, onSubmit, title } = props;
  const { t } = useTranslation();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onSubmit();
      onClose();
    } catch {
      setIsDeleting(false);
    }
  };

  return (
    <AlertModalCore
      isOpen={isOpen}
      handleClose={onClose}
      title={t("wiki.collections.delete_collection")}
      content={
        <p className="text-14 text-secondary">{t("wiki.collections.delete_collection_description", { name: title })}</p>
      }
      primaryButtonText={{
        default: t("common.delete"),
        loading: t("common.loading"),
      }}
      secondaryButtonText={t("common.cancel")}
      isSubmitting={isDeleting}
      handleSubmit={handleDelete}
    />
  );
});

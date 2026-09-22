/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import type { TPageCollection } from "@plane/types";
import { CollectionForm } from "./collection-form";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  data?: TPageCollection;
  onSubmit: (data: { name: string; description: string; access: number }) => Promise<void>;
};

export const CollectionCreateEditModal = observer(function CollectionCreateEditModal(props: Props) {
  const { isOpen, onClose, data, onSubmit } = props;

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.LG}>
      <CollectionForm data={data} onSubmit={onSubmit} onClose={onClose} />
    </ModalCore>
  );
});

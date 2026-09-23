/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@plane/ui";
import type { TPageInstance } from "@/store/pages/base-page";
import { PageShareDialog } from "../page-share-dialog";

type Props = {
  page: TPageInstance;
};

export const PageShareButton = observer(function PageShareButton(props: Props) {
  const { page } = props;
  const [isShareOpen, setIsShareOpen] = useState(false);

  if (!page.canCurrentUserChangeAccess) return null;

  return (
    <>
      <Button variant="outline-primary" size="sm" onClick={() => setIsShareOpen(true)}>
        Share
      </Button>
      {isShareOpen && page.id && (
        <PageShareDialog isOpen={isShareOpen} onClose={() => setIsShareOpen(false)} pageId={page.id} />
      )}
    </>
  );
});

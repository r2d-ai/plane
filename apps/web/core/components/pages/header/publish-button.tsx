/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Button } from "@plane/ui";
import type { TPageInstance } from "@/store/pages/base-page";
import { PagePublishDialog } from "../page-publish-dialog";

type Props = {
  page: TPageInstance;
};

export const PagePublishButton = observer(function PagePublishButton(props: Props) {
  const { page } = props;
  const [isPublishOpen, setIsPublishOpen] = useState(false);

  if (!page.canCurrentUserChangeAccess) return null;

  return (
    <>
      <Button variant="outline-primary" size="sm" onClick={() => setIsPublishOpen(true)}>
        Publish
      </Button>
      {isPublishOpen && page.id && (
        <PagePublishDialog isOpen={isPublishOpen} onClose={() => setIsPublishOpen(false)} pageId={page.id} />
      )}
    </>
  );
});

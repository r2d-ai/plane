/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { SitesPagePublishService } from "@plane/services";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { RichTextEditor } from "@/components/editor/rich-text-editor";

const pagePublishService = new SitesPagePublishService();

const ANCHOR_REGEX = /^[a-zA-Z0-9_-]+$/;

const PublishedWikiPage = observer(function PublishedWikiPage() {
  const { anchor } = useParams<{ anchor: string }>();
  const isAnchorValid = !!anchor && ANCHOR_REGEX.test(anchor);

  const { data, error, isLoading } = useSWR(
    isAnchorValid ? `PUBLIC_WIKI_PAGE_${anchor}` : null,
    isAnchorValid ? () => pagePublishService.retrievePageByAnchor(anchor) : null
  );

  if (isLoading) {
    return (
      <div className="flex h-screen min-h-[500px] w-full items-center justify-center">
        <LogoSpinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-screen min-h-[500px] w-full flex-col items-center justify-center gap-2">
        <h1 className="text-xl font-semibold">Page not found</h1>
        <p className="text-sm text-tertiary">This page has not been published or the link is no longer valid.</p>
      </div>
    );
  }

  const hasContent = data.description_html && data.description_html !== "" && data.description_html !== "<p></p>";

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <h1 className="text-3xl mb-6 font-bold break-words">{data.name}</h1>
      {hasContent && (
        <RichTextEditor
          editable={false}
          anchor={data.anchor}
          id={data.anchor}
          initialValue={data.description_html}
          workspaceId=""
        />
      )}
    </div>
  );
});

export default PublishedWikiPage;

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import useSWR from "swr";
import {
  COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG,
  WORKSPACE_MEMBER_ME_INFORMATION,
  WORKSPACE_MEMBERS,
  WORKSPACE_PROJECTS_ROLES_INFORMATION,
} from "@plane/constants";
import { LogoSpinner } from "@/components/common/logo-spinner";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { resolveWikiScopeAccess } from "../../helpers/wiki-access";
import { useMember } from "@/hooks/store/use-member";
import { useUserPermissions } from "@/hooks/store/user";
import { WikiService } from "@/services/wiki.service";
import { UserService } from "@/services/user.service";

const wikiService = new WikiService();
const userService = new UserService();

export function WikiNotConfigured() {
  const { data: adminStatus } = useSWR("CURRENT_USER_INSTANCE_ADMIN_STATUS", () =>
    userService.currentUserInstanceAdminStatus()
  );
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-18 font-medium text-primary">Wiki is not configured</h1>
      {adminStatus?.is_instance_admin && (
        <p className="text-13 text-secondary">Set COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG to an accessible workspace.</p>
      )}
    </div>
  );
}

type WikiAuthWrapperProps = { workspaceSlug: string; children: ReactNode };

function MemberPreload({ workspaceSlug, children }: WikiAuthWrapperProps) {
  const { fetchUserWorkspaceInfo, fetchUserProjectPermissions } = useUserPermissions();
  const {
    workspace: { fetchWorkspaceMembers },
  } = useMember();
  useSWR(WORKSPACE_MEMBER_ME_INFORMATION(workspaceSlug), () => fetchUserWorkspaceInfo(workspaceSlug));
  useSWR(WORKSPACE_PROJECTS_ROLES_INFORMATION(workspaceSlug), () => fetchUserProjectPermissions(workspaceSlug));
  useSWR(WORKSPACE_MEMBERS(workspaceSlug), () => fetchWorkspaceMembers(workspaceSlug));
  return <>{children}</>;
}

export function WikiAuthWrapper({ workspaceSlug, children }: WikiAuthWrapperProps) {
  const { data: scopes, error, isLoading } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());
  if (isLoading || (!scopes && !error))
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );
  if (error) return <div role="alert">Could not load Wiki access. Please try again.</div>;
  const scope = resolveWikiScopeAccess(scopes ?? [], workspaceSlug);
  if (!scope) {
    if (
      workspaceSlug === COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG &&
      !scopes?.some((item) => item.is_default && item.slug === workspaceSlug)
    ) {
      return <WikiNotConfigured />;
    }
    return <NotAuthorizedView />;
  }
  if (scope.is_member) return <MemberPreload workspaceSlug={workspaceSlug}>{children}</MemberPreload>;
  return <>{children}</>;
}

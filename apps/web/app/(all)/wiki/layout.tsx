import { Outlet, useParams } from "react-router";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";
import { AppRailVisibilityProvider } from "@/lib/app-rail";
import { WorkspaceContentWrapper } from "@/components/workspace/content-wrapper";
import { WikiAuthWrapper } from "@/layouts/auth-layout/wiki-wrapper";

export default function WikiLayout() {
  const { workspaceSlug } = useParams();
  return (
    <AuthenticationWrapper>
      <AppRailVisibilityProvider>
        <WorkspaceContentWrapper>
          {workspaceSlug ? (
            <WikiAuthWrapper workspaceSlug={workspaceSlug}>
              <Outlet />
            </WikiAuthWrapper>
          ) : (
            <Outlet />
          )}
        </WorkspaceContentWrapper>
      </AppRailVisibilityProvider>
    </AuthenticationWrapper>
  );
}

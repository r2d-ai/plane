import { Outlet, useLocation, useParams } from "react-router";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";
import { AppRailVisibilityProvider } from "@/lib/app-rail";
import { WorkspaceContentWrapper } from "@/components/workspace/content-wrapper";
import { WikiShell } from "@/components/wiki";
import { WikiAuthWrapper } from "@/layouts/auth-layout/wiki-wrapper";

export default function WikiLayout() {
  const { workspaceSlug } = useParams();
  const isPersonalList = useLocation().pathname.startsWith("/wiki/personal/");
  return (
    <AuthenticationWrapper>
      <AppRailVisibilityProvider isEnabled>
        <WorkspaceContentWrapper>
          {workspaceSlug ? (
            <WikiAuthWrapper workspaceSlug={workspaceSlug}>
              <WikiShell>
                <Outlet />
              </WikiShell>
            </WikiAuthWrapper>
          ) : isPersonalList ? (
            <WikiShell>
              <Outlet />
            </WikiShell>
          ) : (
            <Outlet />
          )}
        </WorkspaceContentWrapper>
      </AppRailVisibilityProvider>
    </AuthenticationWrapper>
  );
}

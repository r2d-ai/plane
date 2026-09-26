/**
 * @vitest-environment jsdom
 */
import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

const instanceConfig = vi.hoisted(() => ({ is_workspace_dashboards_enabled: false as boolean | undefined }));

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@plane/ui", async () => {
  const { MockCustomSelect, MockUiButton } = await import("../mocks/plane-ui");
  return {
    Button: MockUiButton,
    CustomSelect: MockCustomSelect,
    CustomMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  };
});

vi.mock("@plane/propel/button", async () => {
  const { MockUiButton } = await import("../mocks/plane-ui");
  return { Button: MockUiButton };
});

import { SidebarUserMenu } from "@/components/workspace/sidebar/user-menu";
import { SidebarWorkspaceMenu } from "@/components/workspace/sidebar/workspace-menu";

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "acme" }),
  usePathname: () => "/acme/",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/store/user", () => ({
  useUserPermissions: () => ({
    workspaceUserInfo: { acme: { draft_issue_count: 0 } },
    allowPermissions: () => true,
  }),
  useUser: () => ({ data: { id: "user-1" } }),
}));

vi.mock("@/hooks/store/use-app-theme", () => ({
  useAppTheme: () => ({ isSidebarCollapsed: false, toggleSidebar: vi.fn() }),
}));

vi.mock("@/hooks/use-local-storage", () => ({
  default: () => ({ storedValue: true, setValue: vi.fn() }),
}));

vi.mock("@/components/sidebar/sidebar-navigation", () => ({
  SidebarNavItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/workspace-notifications/notification-app-sidebar-option", () => ({
  NotificationAppSidebarOption: () => null,
}));

vi.mock("@/components/workspace/upgrade-badge", () => ({
  UpgradeBadge: () => null,
}));

vi.mock("@/components/workspace/sidebar/workspace-menu-header", () => ({
  SidebarWorkspaceMenuHeader: () => null,
}));

vi.mock("@/hooks/store/use-instance", () => ({
  useInstance: () => ({
    config:
      instanceConfig.is_workspace_dashboards_enabled === undefined
        ? undefined
        : { is_workspace_dashboards_enabled: instanceConfig.is_workspace_dashboards_enabled },
  }),
}));

describe("workspace dashboards kill-switch UI", () => {
  test("does not render dashboards in user menu when flag is off", () => {
    instanceConfig.is_workspace_dashboards_enabled = false;
    render(<SidebarUserMenu />);
    expect(screen.queryByText("sidebar.dashboards")).toBeNull();
  });

  test("does not render dashboards workspace menu entry when flag is off", () => {
    instanceConfig.is_workspace_dashboards_enabled = false;
    render(<SidebarWorkspaceMenu />);
    expect(screen.queryByText("sidebar.dashboards")).toBeNull();
  });

  test("does not render dashboards workspace menu entry when instance config is missing", () => {
    instanceConfig.is_workspace_dashboards_enabled = undefined;
    render(<SidebarWorkspaceMenu />);
    expect(screen.queryByText("sidebar.dashboards")).toBeNull();
  });

  test("renders dashboards workspace menu entry when flag is on", () => {
    instanceConfig.is_workspace_dashboards_enabled = true;
    render(<SidebarWorkspaceMenu />);
    expect(screen.getByText("sidebar.dashboards")).toBeTruthy();
  });
});

/**
 * @vitest-environment jsdom
 */
import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@plane/ui", async () => {
  const { MockCustomSelect, MockUiButton } = await import("../mocks/plane-ui");
  return {
    Button: MockUiButton,
    CustomSelect: MockCustomSelect,
    EModalPosition: { CENTER: "center" },
    EModalWidth: { LG: "lg" },
    ModalCore: ({ children, isOpen }: { children?: ReactNode; isOpen?: boolean }) =>
      isOpen ? <div data-testid="save-modal">{children}</div> : null,
  };
});

vi.mock("@plane/propel/button", async () => {
  const { MockUiButton } = await import("../mocks/plane-ui");
  return { Button: MockUiButton };
});

vi.mock("@plane/propel/toast", () => ({
  TOAST_TYPE: { SUCCESS: "success", ERROR: "error" },
  setToast: vi.fn(),
}));

vi.mock("swr", () => ({
  default: () => ({
    data: [{ id: "dash-1", name: "Ops" }],
    isLoading: false,
    error: null,
  }),
}));

import SaveInsightToDashboard from "@/components/analytics/v2/save-insight-to-dashboard";
import { SidebarUserMenu } from "@/components/workspace/sidebar/user-menu";

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "acme" }),
  usePathname: () => "/acme/",
}));

vi.mock("@/hooks/store/user", () => ({
  useUserPermissions: () => ({
    workspaceUserInfo: { acme: { draft_issue_count: 0 } },
    allowPermissions: () => true,
  }),
  useUser: () => ({ data: { id: "user-1" } }),
}));

vi.mock("@/hooks/store/use-app-theme", () => ({
  useAppTheme: () => ({ isSidebarCollapsed: false }),
}));

vi.mock("@/components/sidebar/sidebar-navigation", () => ({
  SidebarNavItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/workspace-notifications/notification-app-sidebar-option", () => ({
  NotificationAppSidebarOption: () => null,
}));

vi.mock("@/hooks/store/use-instance", () => ({
  useInstance: () => ({
    config: { is_workspace_dashboards_enabled: false },
  }),
}));

const analyticsQuery = {
  version: 1 as const,
  source: "work_items" as const,
  metrics: [{ key: "work_item_count" as const }],
  dimensions: [{ key: "state" as const }],
};

describe("workspace dashboards kill-switch UI", () => {
  test("does not render save-to-dashboard control when flag is off", () => {
    render(<SaveInsightToDashboard query={analyticsQuery} defaultTitle="Insight" />);
    expect(screen.queryByRole("button", { name: /save to dashboard/i })).toBeNull();
  });

  test("does not render dashboards sidebar entry when flag is off", () => {
    render(<SidebarUserMenu />);
    expect(screen.queryByText("workspace_dashboards")).toBeNull();
    expect(screen.queryByRole("link", { name: /workspace_dashboards/i })).toBeNull();
  });
});

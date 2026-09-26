/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsQueryV2 } from "./analytics";
import type { EDurationFilters } from "./enums";
import type { IIssueActivity, TIssuePriorities } from "./issues";
import type { TIssue } from "./issues/issue";
import type { TIssueRelationTypes } from "./issues/issue_relation";
import type { TStateGroups } from "./state";

export type TWidgetKeys =
  | "overview_stats"
  | "assigned_issues"
  | "created_issues"
  | "issues_by_state_groups"
  | "issues_by_priority"
  | "recent_activity"
  | "recent_projects"
  | "recent_collaborators";

export type TIssuesListTypes = "pending" | "upcoming" | "overdue" | "completed";

// widget filters
export type TAssignedIssuesWidgetFilters = {
  custom_dates?: string[];
  duration?: EDurationFilters;
  tab?: TIssuesListTypes;
};

export type TCreatedIssuesWidgetFilters = {
  custom_dates?: string[];
  duration?: EDurationFilters;
  tab?: TIssuesListTypes;
};

export type TIssuesByStateGroupsWidgetFilters = {
  duration?: EDurationFilters;
  custom_dates?: string[];
};

export type TIssuesByPriorityWidgetFilters = {
  custom_dates?: string[];
  duration?: EDurationFilters;
};

export type TWidgetFiltersFormData =
  | {
      widgetKey: "assigned_issues";
      filters: Partial<TAssignedIssuesWidgetFilters>;
    }
  | {
      widgetKey: "created_issues";
      filters: Partial<TCreatedIssuesWidgetFilters>;
    }
  | {
      widgetKey: "issues_by_state_groups";
      filters: Partial<TIssuesByStateGroupsWidgetFilters>;
    }
  | {
      widgetKey: "issues_by_priority";
      filters: Partial<TIssuesByPriorityWidgetFilters>;
    };

export type TWidget = {
  id: string;
  is_visible: boolean;
  key: TWidgetKeys;
  readonly widget_filters: // only for read
  TAssignedIssuesWidgetFilters &
    TCreatedIssuesWidgetFilters &
    TIssuesByStateGroupsWidgetFilters &
    TIssuesByPriorityWidgetFilters;
  filters: // only for write
  TAssignedIssuesWidgetFilters &
    TCreatedIssuesWidgetFilters &
    TIssuesByStateGroupsWidgetFilters &
    TIssuesByPriorityWidgetFilters;
};

export type TWidgetStatsRequestParams =
  | {
      widget_key: TWidgetKeys;
    }
  | {
      target_date: string;
      issue_type: TIssuesListTypes;
      widget_key: "assigned_issues";
      expand?: "issue_relation";
    }
  | {
      target_date: string;
      issue_type: TIssuesListTypes;
      widget_key: "created_issues";
    }
  | {
      target_date: string;
      widget_key: "issues_by_state_groups";
    }
  | {
      target_date: string;
      widget_key: "issues_by_priority";
    }
  | {
      cursor: string;
      per_page: number;
      search?: string;
      widget_key: "recent_collaborators";
    };

export type TWidgetIssue = TIssue & {
  issue_relation: {
    id: string;
    project_id: string;
    relation_type: TIssueRelationTypes;
    sequence_id: number;
    type_id: string | null;
  }[];
};

// widget stats responses
export type TOverviewStatsWidgetResponse = {
  assigned_issues_count: number;
  completed_issues_count: number;
  created_issues_count: number;
  pending_issues_count: number;
};

export type TAssignedIssuesWidgetResponse = {
  issues: TWidgetIssue[];
  count: number;
};

export type TCreatedIssuesWidgetResponse = {
  issues: TWidgetIssue[];
  count: number;
};

export type TIssuesByStateGroupsWidgetResponse = {
  count: number;
  state: TStateGroups;
};

export type TIssuesByPriorityWidgetResponse = {
  count: number;
  priority: TIssuePriorities;
};

export type TRecentActivityWidgetResponse = IIssueActivity;

export type TRecentProjectsWidgetResponse = string[];

export type TRecentCollaboratorsWidgetResponse = {
  active_issue_count: number;
  user_id: string;
};

export type TWidgetStatsResponse =
  | TOverviewStatsWidgetResponse
  | TIssuesByStateGroupsWidgetResponse[]
  | TIssuesByPriorityWidgetResponse[]
  | TAssignedIssuesWidgetResponse
  | TCreatedIssuesWidgetResponse
  | TRecentActivityWidgetResponse[]
  | TRecentProjectsWidgetResponse
  | TRecentCollaboratorsWidgetResponse[];

// dashboard
export type TDeprecatedDashboard = {
  created_at: string;
  created_by: string | null;
  description_html: string;
  id: string;
  identifier: string | null;
  is_default: boolean;
  name: string;
  owned_by: string;
  type: string;
  updated_at: string;
  updated_by: string | null;
};

export type THomeDashboardResponse = {
  dashboard: TDeprecatedDashboard;
  widgets: TWidget[];
};

// ---------------------------------------------------------------------------
// Workspace dashboards (RD-452 models / RD-453 CRUD API — §27, §33).
// Additive: the legacy home-dashboard types above are untouched.
// ---------------------------------------------------------------------------

export type TDashboardVisibility = "workspace" | "private";

/** §27.1 Dashboard — mirrors `DashboardSerializer` (§33). */
export interface TWorkspaceDashboard {
  id: string;
  workspace?: string;
  name: string;
  description?: string;
  owner?: string;
  visibility: TDashboardVisibility;
  filters?: Record<string, unknown>;
  pql?: string | null;
  default_time_scope?: Record<string, unknown>;
  comparison?: Record<string, unknown>;
  projects?: string[];
  is_favorited?: boolean;
  created_at?: string;
  updated_at?: string;
}

/** §45 P0 widget visualizations available to "save insight to dashboard". */
export type TDashboardWidgetType =
  | "number"
  | "bar"
  | "line"
  | "pie"
  | "donut"
  | "table"
  | "matrix"
  | "statistics"
  | "counter"
  | "gauge"
  | "text"
  | "markdown";

/**
 * §27.3 — the persisted widget query. `query_config` MUST carry a
 * `schema_version`; the AnalyticsQuery V2 body sits alongside it unchanged
 * (§18.2 stores the configuration, never a snapshot of the results).
 */
export interface TDashboardWidgetQueryConfig extends TAnalyticsQueryV2 {
  schema_version: number;
}

export interface TDashboardWidgetPayload {
  title: string;
  description?: string;
  widget_type: TDashboardWidgetType;
  query_config: TDashboardWidgetQueryConfig;
  sort_order?: number;
}

# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.utils import timezone

# Django imports
from django.db import models

# Module imports
from plane.utils.html_processor import strip_tags

from .base import BaseModel


def get_view_props():
    return {"full_width": False}


class Page(BaseModel):
    PRIVATE_ACCESS = 1
    PUBLIC_ACCESS = 0
    DEFAULT_SORT_ORDER = 65535

    PROJECT_SCOPE = "project"
    WIKI_SCOPE = "wiki"

    ACCESS_CHOICES = ((PRIVATE_ACCESS, "Private"), (PUBLIC_ACCESS, "Public"))

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="pages")
    name = models.TextField(blank=True)
    description_json = models.JSONField(default=dict, blank=True)
    description_binary = models.BinaryField(null=True)
    description_html = models.TextField(blank=True, default="<p></p>")
    description_stripped = models.TextField(blank=True, null=True)
    owned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pages")
    access = models.PositiveSmallIntegerField(choices=((0, "Public"), (1, "Private")), default=0)
    color = models.CharField(max_length=255, blank=True)
    labels = models.ManyToManyField("db.Label", blank=True, related_name="pages", through="db.PageLabel")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_page",
    )
    archived_at = models.DateField(null=True)
    is_locked = models.BooleanField(default=False)
    view_props = models.JSONField(default=get_view_props)
    logo_props = models.JSONField(default=dict)
    is_global = models.BooleanField(default=False)
    projects = models.ManyToManyField("db.Project", related_name="pages", through="db.ProjectPage")
    moved_to_page = models.UUIDField(null=True, blank=True)
    moved_to_project = models.UUIDField(null=True, blank=True)
    sort_order = models.FloatField(default=DEFAULT_SORT_ORDER)

    external_id = models.CharField(max_length=255, null=True, blank=True)
    external_source = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        db_table = "pages"
        ordering = ("-created_at",)
        indexes = [
            # WIKI-04b: measured index for the Workspace/Company Wiki access
            # paths (spec §21 candidate `(workspace_id, is_global, archived_at)`).
            # `EXPLAIN (ANALYZE)` on the 1k/5k/deep/wide fixtures shows the
            # planner using this index for the permission-filtered Wiki list
            # (`archived_at IS NULL`) and the Archived section
            # (`archived_at IS NOT NULL`, ~4x); the other §21 candidates were
            # either not selected or measured slower. See
            # docs/wiki-ce-performance-report.md.
            models.Index(
                fields=["workspace", "is_global", "archived_at"],
                name="pages_wiki_scope_idx",
            ),
        ]

    def __str__(self):
        """Return owner email and page name"""
        return f"{self.owned_by.email} <{self.name}>"

    @property
    def scope(self):
        """Storage scope of the page.

        ``project`` for Project Pages (``is_global=False``) and ``wiki`` for
        Workspace/Company Wiki pages (``is_global=True``). Company Wiki is
        Workspace Wiki on the designated workspace, so it also reports ``wiki``.
        """
        return self.WIKI_SCOPE if self.is_global else self.PROJECT_SCOPE

    @property
    def is_project_page(self):
        """True for Project Pages, which must have an active ProjectPage link."""
        return not self.is_global

    @property
    def is_workspace_page(self):
        """True for Wiki pages (Workspace Wiki and Company Wiki).

        Wiki pages belong to a real workspace but require no ProjectPage link.
        """
        return self.is_global

    def save(self, *args, **kwargs):
        # Strip the html tags using html parser
        self.description_stripped = (
            None
            if (self.description_html == "" or self.description_html is None)
            else strip_tags(self.description_html)
        )
        super(Page, self).save(*args, **kwargs)


class PageLog(BaseModel):
    TYPE_CHOICES = (
        ("to_do", "To Do"),
        ("issue", "issue"),
        ("image", "Image"),
        ("video", "Video"),
        ("file", "File"),
        ("link", "Link"),
        ("cycle", "Cycle"),
        ("module", "Module"),
        ("back_link", "Back Link"),
        ("forward_link", "Forward Link"),
        ("page_mention", "Page Mention"),
        ("user_mention", "User Mention"),
    )
    transaction = models.UUIDField(default=uuid.uuid4)
    page = models.ForeignKey(Page, related_name="page_log", on_delete=models.CASCADE)
    entity_identifier = models.UUIDField(null=True, blank=True)
    entity_name = models.CharField(max_length=30, verbose_name="Transaction Type")
    entity_type = models.CharField(max_length=30, verbose_name="Entity Type", null=True, blank=True)
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workspace_page_log")

    class Meta:
        unique_together = ["page", "transaction"]
        verbose_name = "Page Log"
        verbose_name_plural = "Page Logs"
        db_table = "page_logs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["entity_type"], name="pagelog_entity_type_idx"),
            models.Index(fields=["entity_identifier"], name="pagelog_entity_id_idx"),
            models.Index(fields=["entity_name"], name="pagelog_entity_name_idx"),
            models.Index(fields=["entity_type", "entity_identifier"], name="pagelog_type_id_idx"),
            models.Index(fields=["entity_name", "entity_identifier"], name="pagelog_name_id_idx"),
        ]

    def __str__(self):
        return f"{self.page.name} {self.entity_name}"


class PageLabel(BaseModel):
    label = models.ForeignKey("db.Label", on_delete=models.CASCADE, related_name="page_labels")
    page = models.ForeignKey("db.Page", on_delete=models.CASCADE, related_name="page_labels")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workspace_page_label")

    class Meta:
        verbose_name = "Page Label"
        verbose_name_plural = "Page Labels"
        db_table = "page_labels"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.page.name} {self.label.name}"


class ProjectPage(BaseModel):
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="project_pages")
    page = models.ForeignKey("db.Page", on_delete=models.CASCADE, related_name="project_pages")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="project_pages")

    class Meta:
        unique_together = ["project", "page", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "page"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_page_unique_project_page_when_deleted_at_null",
            )
        ]
        verbose_name = "Project Page"
        verbose_name_plural = "Project Pages"
        db_table = "project_pages"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.project.name} {self.page.name}"


class PageCollection(BaseModel):
    """Workspace-level Wiki grouping primitive (spec §5.5, §19; plan §8.2).

    A Collection belongs to exactly one workspace and never mixes the designated
    Company Wiki workspace with another: every relation below carries the same
    ``workspace`` as the collection so a Collection can never leak a page across
    scopes (WIKI-05, decision D6).

    Access semantics (open question Q8 in ``docs/wiki-ce-spec.md``):
    - ``access=PRIVATE`` makes the collection a mandatory authorization boundary
      for every page in its (inherited) subtree;
    - ``access=PUBLIC`` keeps the collection visible to workspace members and
      adds grouping only.
    """

    ACCESS_PUBLIC = 0
    ACCESS_PRIVATE = 1
    ACCESS_CHOICES = ((ACCESS_PUBLIC, "Public"), (ACCESS_PRIVATE, "Private"))

    DEFAULT_SORT_ORDER = 65535

    # Collection member roles map onto effective page capabilities (spec §19.1).
    ROLE_VIEW = 5
    ROLE_COMMENT = 10
    ROLE_EDIT = 15
    ROLE_CHOICES = ((ROLE_VIEW, "View"), (ROLE_COMMENT, "Comment"), (ROLE_EDIT, "Edit"))

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_collections")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    logo_props = models.JSONField(default=dict)
    access = models.PositiveSmallIntegerField(choices=ACCESS_CHOICES, default=ACCESS_PUBLIC)
    sort_order = models.FloatField(default=DEFAULT_SORT_ORDER)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Page Collection"
        verbose_name_plural = "Page Collections"
        db_table = "page_collections"
        ordering = ("sort_order", "-created_at")
        constraints = [
            # A default collection may exist per workspace (spec §5.5).
            models.UniqueConstraint(
                fields=["workspace"],
                condition=models.Q(is_default=True, deleted_at__isnull=True),
                name="page_collection_unique_default_per_workspace",
            ),
            # Collection names are unique inside a workspace while alive.
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="page_collection_unique_name_per_workspace",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "sort_order"], name="page_collection_ws_sort_idx"),
            models.Index(fields=["workspace", "access"], name="page_collection_ws_access_idx"),
        ]

    def __str__(self):
        return f"{self.workspace_id} <{self.name}>"

    @property
    def is_private(self):
        return self.access == self.ACCESS_PRIVATE


class PageCollectionMember(BaseModel):
    """Membership + role of a user inside a Collection (spec §5.5)."""

    VIEW = PageCollection.ROLE_VIEW
    COMMENT = PageCollection.ROLE_COMMENT
    EDIT = PageCollection.ROLE_EDIT
    ROLE_CHOICES = PageCollection.ROLE_CHOICES

    collection = models.ForeignKey(PageCollection, on_delete=models.CASCADE, related_name="members")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="page_collection_memberships",
    )
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_collection_members")
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=VIEW)

    class Meta:
        verbose_name = "Page Collection Member"
        verbose_name_plural = "Page Collection Members"
        db_table = "page_collection_members"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="page_collection_member_unique_collection_member",
            )
        ]
        indexes = [
            models.Index(fields=["collection", "member"], name="page_coll_member_lookup_idx"),
            models.Index(fields=["workspace", "member"], name="page_coll_member_ws_idx"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if self.collection_id and self.workspace_id and self.collection.workspace_id != self.workspace_id:
            raise DjangoValidationError("Collection member must belong to the collection's workspace.")

    def save(self, *args, **kwargs):
        if self.collection_id:
            self.workspace_id = self.collection.workspace_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.collection_id} {self.member_id} {self.role}"


class PageCollectionPage(BaseModel):
    """Association + order of a page inside a Collection (spec §5.5).

    Exactly one Collection may own a page at a time: the conditional unique
    constraint on ``page`` is what makes the spec's "must not accidentally
    support multi-collection membership" guarantee enforceable in the DB
    (open question Q8). Descendants inherit the nearest ancestor's Collection
    through the Page hierarchy, so this table stores boundaries only.
    """

    collection = models.ForeignKey(PageCollection, on_delete=models.CASCADE, related_name="collection_pages")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="collection_pages")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_collection_pages")
    sort_order = models.FloatField(default=Page.DEFAULT_SORT_ORDER)

    class Meta:
        verbose_name = "Page Collection Page"
        verbose_name_plural = "Page Collection Pages"
        db_table = "page_collection_pages"
        ordering = ("sort_order", "-created_at")
        constraints = [
            # A page belongs to at most one Collection (Q8).
            models.UniqueConstraint(
                fields=["page"],
                condition=models.Q(deleted_at__isnull=True),
                name="page_collection_page_unique_page",
            ),
            models.UniqueConstraint(
                fields=["collection", "page"],
                condition=models.Q(deleted_at__isnull=True),
                name="page_collection_page_unique_collection_page",
            ),
        ]
        indexes = [
            models.Index(fields=["collection", "sort_order"], name="page_coll_page_coll_sort_idx"),
            models.Index(fields=["workspace", "page"], name="page_coll_page_ws_page_idx"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if self.collection_id and self.workspace_id and self.collection.workspace_id != self.workspace_id:
            raise DjangoValidationError("Collection page must belong to the collection's workspace.")
        if self.page_id and self.workspace_id and self.page.workspace_id != self.workspace_id:
            raise DjangoValidationError("Collection page must belong to the collection's workspace.")

    def save(self, *args, **kwargs):
        if self.collection_id:
            self.workspace_id = self.collection.workspace_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.collection_id} {self.page_id}"


class PageShare(BaseModel):
    """Direct named-user share of a Workspace/Company Wiki page (spec §5.3).

    A share grants a ``VIEW`` / ``COMMENT`` / ``EDIT`` capability on one page to
    one workspace member and is folded into the centralized effective-capability
    algorithm in ``plane.utils.page_access``. It never bypasses a private
    Collection boundary (spec §19.1).

    Constraints (spec §5.3):
    - at most one active share per ``(page, member)``;
    - the shared member must belong to the page's workspace (validated in
      ``clean`` and re-checked by the API);
    - the page must be a workspace Wiki page (``is_global=True``);
    - the owner does not need a share row to see the page.
    """

    ROLE_VIEW = PageCollection.ROLE_VIEW
    ROLE_COMMENT = PageCollection.ROLE_COMMENT
    ROLE_EDIT = PageCollection.ROLE_EDIT
    VIEW = ROLE_VIEW
    COMMENT = ROLE_COMMENT
    EDIT = ROLE_EDIT
    ROLE_CHOICES = PageCollection.ROLE_CHOICES

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_shares")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="shares")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="page_shares",
    )
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=VIEW)

    class Meta:
        verbose_name = "Page Share"
        verbose_name_plural = "Page Shares"
        db_table = "page_shares"
        ordering = ("-created_at",)
        constraints = [
            # One active share per (page, member); a removed share can be
            # re-created without leaving dangling rows behind.
            models.UniqueConstraint(
                fields=["page", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="page_share_unique_page_member",
            ),
        ]
        indexes = [
            # Spec §21 candidate `(page_id, member_id)` for shares.
            models.Index(fields=["page", "member"], name="page_share_page_member_idx"),
            models.Index(fields=["workspace", "member"], name="page_share_ws_member_idx"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if self.page_id and self.workspace_id and self.page.workspace_id != self.workspace_id:
            raise DjangoValidationError("Page share must belong to the page's workspace.")
        if self.page_id and not self.page.is_global:
            raise DjangoValidationError("Page share must target a workspace Wiki page.")
        if self.workspace_id and self.member_id:
            from .workspace import WorkspaceMember

            if not WorkspaceMember.objects.filter(
                workspace_id=self.workspace_id, member_id=self.member_id, is_active=True
            ).exists():
                raise DjangoValidationError("Shared member must be an active member of the page's workspace.")

    def save(self, *args, **kwargs):
        # The page (and its workspace) are the source of truth, exactly like
        # PageCollectionMember: a share can never point at another workspace.
        if self.page_id:
            self.workspace_id = self.page.workspace_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.page_id} {self.member_id} {self.role}"


class PageComment(BaseModel):
    """Page-level comment for Workspace/Company Wiki pages (spec §5.4, §14).

    Permissions derive from effective Page access. The owner of a comment may
    edit or delete it. Replies are supported via ``parent`` self-FK for
    threaded conversations.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_comments")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="page_comments")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="page_comments",
    )
    comment_html = models.TextField(blank=True, default="<p></p>")
    comment_json = models.JSONField(default=dict, blank=True)
    comment_stripped = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="parent_page_comment",
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    # Moderation state (WIKI-09b, plan §12.5). A hidden comment is never
    # deleted: the row, its body and its audit trail are preserved, only
    # visibility changes. `hidden_reason`/`hidden_by` mirror the latest
    # moderation action so a list can render it without joining the log.
    is_hidden = models.BooleanField(default=False)
    hidden_reason = models.CharField(max_length=255, blank=True, default="")
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_page_comments",
    )

    class Meta:
        verbose_name = "Page Comment"
        verbose_name_plural = "Page Comments"
        db_table = "page_comments"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["page", "created_at"], name="page_comment_page_created_idx"),
            models.Index(fields=["workspace", "page"], name="page_comment_ws_page_idx"),
            # Moderation lists filter hidden/visible comments per page.
            models.Index(fields=["page", "is_hidden", "created_at"], name="page_comment_page_hidden_idx"),
        ]

    def save(self, *args, **kwargs):
        from plane.utils.html_processor import strip_tags

        self.comment_stripped = (
            None if (self.comment_html == "" or self.comment_html is None) else strip_tags(self.comment_html)
        )
        super(PageComment, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.page_id} by {self.actor_id}"


class PageCommentModeration(BaseModel):
    """Append-only audit trail of comment moderation actions (WIKI-09b §12.5).

    Every hide/unhide writes one row, so the moderation history survives: who
    acted, when, why, and which action. The comment itself is never deleted, so
    hiding is fully reversible and the original body stays available to
    workspace admins.
    """

    ACTION_HIDE = "hide"
    ACTION_UNHIDE = "unhide"
    ACTION_CHOICES = ((ACTION_HIDE, "Hide"), (ACTION_UNHIDE, "Unhide"))

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_comment_moderations")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="comment_moderations")
    comment = models.ForeignKey(PageComment, on_delete=models.CASCADE, related_name="moderation_log")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_comment_moderations",
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Page Comment Moderation"
        verbose_name_plural = "Page Comment Moderations"
        db_table = "page_comment_moderations"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["comment", "created_at"], name="page_comment_mod_comment_idx"),
            models.Index(fields=["page", "created_at"], name="page_comment_mod_page_idx"),
        ]

    def __str__(self):
        return f"{self.comment_id} {self.action}"


class PageView(BaseModel):
    """A single counted page view for Wiki analytics (WIKI-09b, plan §12.3).

    One row per *counted* view. A background preload never reaches this table:
    the record endpoint short-circuits before insert, so aggregates cannot be
    inflated by non-user reads. ``viewer`` is filled only when the deployment
    policy permits viewer identification (``PAGE_ANALYTICS_IDENTIFY_VIEWERS``);
    otherwise it stays NULL and aggregates report anonymous views only.

    ``collection`` is the nearest Collection boundary at view time, denormalized
    so Collection roll-ups do not have to re-walk the Page hierarchy. A page
    that later moves Collections keeps its historical bucket, which is the
    intended "as viewed" semantics.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_views")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="views")
    collection = models.ForeignKey(
        PageCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_views",
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_views",
    )
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Page View"
        verbose_name_plural = "Page Views"
        db_table = "page_views"
        ordering = ("-viewed_at",)
        indexes = [
            # Page timeline + page total (measured query plan, WIKI-09b).
            models.Index(fields=["page", "viewed_at"], name="page_view_page_viewed_idx"),
            # Collection roll-up (measured query plan, WIKI-09b).
            models.Index(fields=["collection", "viewed_at"], name="page_view_coll_viewed_idx"),
        ]

    def __str__(self):
        return f"{self.page_id} @ {self.viewed_at}"


class PageVersion(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_versions")
    page = models.ForeignKey("db.Page", on_delete=models.CASCADE, related_name="page_versions")
    last_saved_at = models.DateTimeField(default=timezone.now)
    owned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="page_versions")
    description_binary = models.BinaryField(null=True)
    description_html = models.TextField(blank=True, default="<p></p>")
    description_stripped = models.TextField(blank=True, null=True)
    description_json = models.JSONField(default=dict, blank=True)
    sub_pages_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Page Version"
        verbose_name_plural = "Page Versions"
        db_table = "page_versions"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        # Strip the html tags using html parser
        self.description_stripped = (
            None
            if (self.description_html == "" or self.description_html is None)
            else strip_tags(self.description_html)
        )
        super(PageVersion, self).save(*args, **kwargs)


class PageTemplate(BaseModel):
    """Workspace-scoped Wiki page template (spec §16; plan §10.1).

    A template is a workspace-owned snapshot of a page's document content that
    any member of the workspace can instantiate. It stores the exact same
    ``description_*`` triplet as ``Page`` so the document engine is never
    duplicated (spec §16): creating a page from a template copies those fields
    into a new ``Page`` row.

    ``workspace`` is mandatory and every lookup is scoped to the URL workspace,
    so a template UUID from another workspace can never be resolved (BOLA/IDOR
    invariant, spec §6.2).
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="page_templates")
    name = models.CharField(max_length=255)
    description_json = models.JSONField(default=dict, blank=True)
    description_binary = models.BinaryField(null=True)
    description_html = models.TextField(blank=True, default="<p></p>")
    description_stripped = models.TextField(blank=True, null=True)
    logo_props = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Page Template"
        verbose_name_plural = "Page Templates"
        db_table = "page_templates"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "created_at"], name="page_template_ws_created_idx"),
        ]

    def save(self, *args, **kwargs):
        # Strip the html tags using html parser
        self.description_stripped = (
            None
            if (self.description_html == "" or self.description_html is None)
            else strip_tags(self.description_html)
        )
        super(PageTemplate, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id} <{self.name}>"


class WikiEvent(BaseModel):
    """Append-only Wiki integration event feed (WIKI-10, spec §20).

    AI/provider integrations and importers consume Wiki state through this
    durable event log and the read APIs in ``plane.utils.wiki_ai`` instead of
    reading the ``Page`` tables directly, so the Wiki schema can evolve without
    coupling an external service to it (plan §13.1 "stable APIs/events").

    Events are workspace-scoped; ``payload`` carries identifiers and metadata
    only and never embeds ``description_html``/``description_json``, so a
    private page body can never leak through the feed (spec §20, §22.5).
    ``page`` is ``SET_NULL`` and ``page_name`` is a snapshot so the trail
    survives a hard delete.
    """

    PAGE_CREATED = "page.created"
    PAGE_UPDATED = "page.updated"
    PAGE_MOVED = "page.moved"
    PAGE_ARCHIVED = "page.archived"
    PAGE_RESTORED = "page.restored"
    PAGE_DELETED = "page.deleted"
    PAGE_ACCESS_CHANGED = "page.access_changed"
    PAGE_IMPORTED = "page.imported"
    PAGE_AI_EDIT = "page.ai_edit"

    EVENT_CHOICES = (
        (PAGE_CREATED, "Page Created"),
        (PAGE_UPDATED, "Page Updated"),
        (PAGE_MOVED, "Page Moved"),
        (PAGE_ARCHIVED, "Page Archived"),
        (PAGE_RESTORED, "Page Restored"),
        (PAGE_DELETED, "Page Deleted"),
        (PAGE_ACCESS_CHANGED, "Page Access Changed"),
        (PAGE_IMPORTED, "Page Imported"),
        (PAGE_AI_EDIT, "Page AI Edit"),
    )

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="wiki_events")
    page = models.ForeignKey(
        "db.Page",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiki_events",
    )
    page_name = models.CharField(max_length=255, blank=True, default="")
    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiki_events",
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Wiki Event"
        verbose_name_plural = "Wiki Events"
        db_table = "wiki_events"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "created_at"], name="wiki_event_ws_created_idx"),
            models.Index(fields=["workspace", "event_type", "created_at"], name="wiki_event_ws_type_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} {self.page_name}"

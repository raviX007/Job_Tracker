"use client";

import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  getEmailQueue,
  getEmailStatuses,
  getEmailSources,
  updateEmailContent,
  deleteEmail,
  deleteAllEmails,
  sendEmail,
} from "@/lib/api";
import { useProfile, isDemoMode } from "@/hooks/use-profile";
import { useAuth } from "@/hooks/use-auth";
import { queryKeys } from "@/lib/query-keys";
import { cn, statusColor, scoreBadgeColor, formatDateTime } from "@/lib/utils";
import { EMAIL_STATUSES } from "@/lib/constants";
import { PageHeader } from "@/components/layout/page-header";
import type { EmailQueueItem, EmailStatusCounts, PaginatedResult } from "@/lib/types";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Pagination } from "@/components/ui/pagination";
import { SkeletonCard } from "@/components/ui/skeletons";

// ─── Loading skeleton ────────────────────────────────

function EmailsSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-20 rounded-full" />
        ))}
      </div>
      <Card>
        <CardContent className="flex items-center gap-4 py-4">
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-9 w-40" />
        </CardContent>
      </Card>
      {Array.from({ length: 3 }).map((_, i) => (
        <SkeletonCard key={i} lines={2} />
      ))}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────

export default function EmailsPage() {
  const { profileId } = useProfile();
  const demo = isDemoMode();
  const { canEdit } = useAuth();
  const readOnly = demo || !canEdit;

  const queryClient = useQueryClient();

  // Filters
  const [filterStatus, setFilterStatus] = useState("All");
  const [filterSource, setFilterSource] = useState("All");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  // Editing state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");

  // Collapsible state (track which emails are expanded)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  // Dialog open states
  const [deleteDialogId, setDeleteDialogId] = useState<number | null>(null);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);

  // Success flash
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  // Reset page when filters change
  const resetPage = () => setPage(1);

  // ── Fetching ──────────────────────────────────────

  const queryKey = [...queryKeys.emails(profileId, filterStatus, filterSource), page, pageSize] as const;

  const { data: paginatedEmails, isLoading: loadingEmails, error: emailsError, refetch: refetchEmails } = useQuery({
    queryKey,
    queryFn: ({ signal }) => getEmailQueue(profileId, filterStatus, filterSource, pageSize, (page - 1) * pageSize, signal),
  });

  const emails = paginatedEmails?.data ?? [];
  const totalCount = paginatedEmails?.totalCount ?? 0;

  const { data: statusCounts = {} as EmailStatusCounts } = useQuery({
    queryKey: queryKeys.emailStatuses(profileId),
    queryFn: ({ signal }) => getEmailStatuses(profileId, signal),
  });

  const { data: sources = [] } = useQuery({
    queryKey: queryKeys.emailSources(profileId),
    queryFn: ({ signal }) => getEmailSources(profileId, signal),
  });

  const loading = loadingEmails;

  // ── Shared invalidation for onSettled ─────────────

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
    queryClient.invalidateQueries({ queryKey: queryKeys.emailStatuses(profileId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.emailSources(profileId) });
  };

  // ── Mutations ─────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: ({ emailId, subject, body }: { emailId: number; subject: string; body: string }) =>
      updateEmailContent(emailId, subject, body),
    onMutate: async ({ emailId, subject, body }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
      const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
          ...prev,
          data: prev.data.map(e => e.id === emailId ? { ...e, subject, body_plain: body } : e),
        });
      }
      cancelEditing();
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
    },
    onSettled: invalidateAll,
    onSuccess: () => showSuccess("Email updated"),
  });

  const sendMutation = useMutation({
    mutationFn: ({ emailId }: { emailId: number }) => sendEmail(emailId),
    onMutate: async ({ emailId }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
      const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
          ...prev,
          data: prev.data.map(e => e.id === emailId ? { ...e, status: "sent" } : e),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
    },
    onSettled: invalidateAll,
    onSuccess: (result) => showSuccess(`Sent to ${result.to}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (emailId: number) => deleteEmail(emailId),
    onMutate: async (emailId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
      const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
          ...prev,
          data: prev.data.filter(e => e.id !== emailId),
          totalCount: prev.totalCount - 1,
        });
      }
      setDeleteDialogId(null);
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
    },
    onSettled: invalidateAll,
    onSuccess: () => showSuccess("Email deleted"),
  });

  const deleteAllMutation = useMutation({
    mutationFn: () => deleteAllEmails(profileId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
      const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
          ...prev,
          data: [],
          totalCount: 0,
        });
      }
      setDeleteAllDialogOpen(false);
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
    },
    onSettled: invalidateAll,
    onSuccess: (result) => showSuccess(`Deleted ${result.deleted} emails`),
  });

  // ── Combined error ────────────────────────────────

  const mutationError = saveMutation.error?.message || sendMutation.error?.message || deleteMutation.error?.message || deleteAllMutation.error?.message;
  const error = emailsError?.message ?? mutationError ?? null;

  // ── Toggle expand ─────────────────────────────────

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // ── Start editing ─────────────────────────────────

  const startEditing = (email: EmailQueueItem) => {
    setEditingId(email.id);
    setEditSubject(email.subject);
    setEditBody(email.body_plain);
    // Expand if not already
    setExpandedIds((prev) => new Set(prev).add(email.id));
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditSubject("");
    setEditBody("");
  };

  // ── Render ────────────────────────────────────────

  return (
    <div>
      <PageHeader title="Cold Emails" subtitle="Email queue management" />

      {/* Success message */}
      {successMsg && (
        <Card className="mb-4 border-emerald-200 bg-emerald-50">
          <CardContent className="py-3">
            <p className="text-sm text-emerald-700">{successMsg}</p>
          </CardContent>
        </Card>
      )}

      {/* Error state */}
      {error && (
        <Card className="mb-4 border-red-200 bg-red-50">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm text-red-700">{error}</p>
            <Button variant="outline" size="sm" onClick={() => refetchEmails()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading */}
      {loading && <EmailsSkeleton />}

      {/* Loaded content */}
      {!loading && (
        <div className="space-y-4">
          {/* ── Status summary bar ──────────────────── */}
          <div className="flex flex-wrap gap-2">
            {Object.entries(statusCounts).map(([status, count]) => (
              <Badge key={status} className={cn("text-xs", statusColor(status))}>
                {status}: {count}
              </Badge>
            ))}
            {Object.keys(statusCounts).length === 0 && (
              <p className="text-sm text-muted-foreground">No status data</p>
            )}
          </div>

          {/* ── Filter row ──────────────────────────── */}
          <Card>
            <CardContent className="flex flex-wrap items-center gap-4 py-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-muted-foreground">Status:</span>
                <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); resetPage(); }}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EMAIL_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s === "All" ? "All Statuses" : s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-muted-foreground">Source:</span>
                <Select value={filterSource} onValueChange={(v) => { setFilterSource(v); resetPage(); }}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="All">All Sources</SelectItem>
                    {sources.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* ── Email list ──────────────────────────── */}
          {emails.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-sm text-muted-foreground">No emails in queue</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {emails.map((email) => {
                const isExpanded = expandedIds.has(email.id);
                const isEditing = editingId === email.id;

                return (
                  <Card key={email.id} className="hover:shadow-md transition-shadow">
                    <CardHeader className="pb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge className={cn("text-xs", statusColor(email.status))}>
                          {email.status}
                        </Badge>
                        {email.email_verified && (
                          <Badge variant="outline" className="text-xs border-blue-300 text-blue-600">
                            verified
                          </Badge>
                        )}
                        <span className="font-semibold text-gray-900">
                          {email.recipient_name}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {email.recipient_email}
                        </span>
                        {email.recipient_role && (
                          <span className="text-xs text-muted-foreground">
                            ({email.recipient_role})
                          </span>
                        )}
                      </div>

                      {/* Company + job info */}
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <span className="font-medium text-gray-700">{email.job_company}</span>
                        <span>&middot;</span>
                        <span>{email.job_title}</span>
                        <span>&middot;</span>
                        <span>{email.job_source}</span>
                        <div
                          className={cn(
                            "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white",
                            scoreBadgeColor(email.match_score),
                          )}
                        >
                          {email.match_score}
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-3">
                      {/* Toggle expand button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleExpand(email.id)}
                        className="text-xs text-muted-foreground"
                      >
                        {isExpanded ? "Hide content" : "Show content"}
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className={cn("ml-1 transition-transform", isExpanded && "rotate-180")}
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </Button>

                      {/* Collapsible content */}
                      {isExpanded && (
                        <div className="rounded-md border bg-gray-50 p-4">
                          {isEditing ? (
                            <div className="space-y-3">
                              <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                                  Subject
                                </label>
                                <Input
                                  value={editSubject}
                                  onChange={(e) => setEditSubject(e.target.value)}
                                  placeholder="Email subject"
                                />
                              </div>
                              <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                                  Body
                                </label>
                                <Textarea
                                  value={editBody}
                                  onChange={(e) => setEditBody(e.target.value)}
                                  rows={8}
                                  placeholder="Email body"
                                />
                              </div>
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  onClick={() => saveMutation.mutate({ emailId: email.id, subject: editSubject, body: editBody })}
                                  disabled={readOnly || (saveMutation.isPending && saveMutation.variables?.emailId === email.id)}
                                >
                                  {saveMutation.isPending && saveMutation.variables?.emailId === email.id ? "Saving..." : "Save"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={cancelEditing}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div>
                              <p className="font-semibold text-gray-900">{email.subject}</p>
                              <Separator className="my-2" />
                              <p className="whitespace-pre-wrap text-sm text-gray-700">
                                {email.body_plain}
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Edit button */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (isEditing) {
                              cancelEditing();
                            } else {
                              startEditing(email);
                            }
                          }}
                          disabled={readOnly}
                          title={demo ? "Disabled in demo mode" : "Edit email"}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="mr-1"
                          >
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                          </svg>
                          {isEditing ? "Cancel Edit" : "Edit"}
                        </Button>

                        {/* Send button (only for ready status) */}
                        {email.status === "ready" && (
                          <Button
                            size="sm"
                            onClick={() => sendMutation.mutate({ emailId: email.id })}
                            disabled={readOnly || (sendMutation.isPending && sendMutation.variables?.emailId === email.id)}
                            title={demo ? "Disabled in demo mode" : "Send email"}
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className="mr-1"
                            >
                              <line x1="22" y1="2" x2="11" y2="13" />
                              <polygon points="22 2 15 22 11 13 2 9 22 2" />
                            </svg>
                            {sendMutation.isPending && sendMutation.variables?.emailId === email.id ? "Sending..." : "Send"}
                          </Button>
                        )}

                        {/* Delete button with confirmation dialog */}
                        <Dialog
                          open={deleteDialogId === email.id}
                          onOpenChange={(open) => setDeleteDialogId(open ? email.id : null)}
                        >
                          <DialogTrigger asChild>
                            <Button
                              variant="destructive"
                              size="sm"
                              disabled={readOnly || (deleteMutation.isPending && deleteMutation.variables === email.id)}
                              title={demo ? "Disabled in demo mode" : "Delete email"}
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="mr-1"
                              >
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              </svg>
                              {deleteMutation.isPending && deleteMutation.variables === email.id ? "Deleting..." : "Delete"}
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Delete Email</DialogTitle>
                              <DialogDescription>
                                Are you sure you want to delete this email to{" "}
                                <span className="font-medium">{email.recipient_name}</span> at{" "}
                                <span className="font-medium">{email.job_company}</span>?
                                This action cannot be undone.
                              </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <Button
                                variant="ghost"
                                onClick={() => setDeleteDialogId(null)}
                              >
                                Cancel
                              </Button>
                              <Button
                                variant="destructive"
                                onClick={() => deleteMutation.mutate(email.id)}
                              >
                                Delete
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </div>

                      {/* Timestamps */}
                      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                        <span>Created: {formatDateTime(email.created_at)}</span>
                        {email.sent_at && <span>Sent: {formatDateTime(email.sent_at)}</span>}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* ── Pagination ──────────────────────────── */}
          <Pagination
            page={page}
            pageSize={pageSize}
            total={totalCount}
            onPageChange={setPage}
          />

          {/* ── Delete All ──────────────────────────── */}
          {emails.length > 0 && (
            <div className="flex justify-end pt-4">
              <Dialog
                open={deleteAllDialogOpen}
                onOpenChange={setDeleteAllDialogOpen}
              >
                <DialogTrigger asChild>
                  <Button
                    variant="destructive"
                    disabled={readOnly || deleteAllMutation.isPending}
                    title={demo ? "Disabled in demo mode" : "Delete all emails"}
                  >
                    {deleteAllMutation.isPending ? "Deleting All..." : "Delete All Emails"}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete All Emails</DialogTitle>
                    <DialogDescription>
                      Are you sure you want to delete all emails in the queue? This will remove{" "}
                      <span className="font-bold">{emails.length}</span> email(s).
                      This action cannot be undone.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button
                      variant="ghost"
                      onClick={() => setDeleteAllDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button variant="destructive" onClick={() => deleteAllMutation.mutate()}>
                      Delete All
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { getTrackerData, upsertApplication, markJobObsolete } from "@/lib/api";
import { useProfile } from "@/hooks/use-profile";
import { useAuth } from "@/hooks/use-auth";
import { queryKeys } from "@/lib/query-keys";
import { cn, scoreBadgeColor, decisionColor } from "@/lib/utils";
import { APPLICATION_METHODS, RESPONSE_TYPES } from "@/lib/constants";
import { exportToExcel } from "@/lib/export";
import { PageHeader } from "@/components/layout/page-header";
import type { TrackerRow, PaginatedResult } from "@/lib/types";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { Pagination } from "@/components/ui/pagination";
import { SkeletonTable } from "@/components/ui/skeletons";

// ─── Types ───────────────────────────────────────────

interface RowEdits {
  method: string;
  platform: string;
  response_type: string;
  notes: string;
}

// ─── Loading skeleton ────────────────────────────────

const TRACKER_COLUMNS = [
  "Score", "Decision", "Company", "Title", "Source",
  "Method", "Platform", "Status", "Notes", "Actions",
];

function TrackerSkeleton() {
  return <SkeletonTable rows={8} columns={TRACKER_COLUMNS} />;
}

// ─── Page ────────────────────────────────────────────

export default function TrackerPage() {
  const { profileId } = useProfile();
  const { canEdit } = useAuth();
  const queryClient = useQueryClient();
  const [showObsolete, setShowObsolete] = useState(false);
  const [edits, setEdits] = useState<Record<number, RowEdits>>({});
  const [savedRows, setSavedRows] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data: paginatedResult, isLoading: loading, error: queryError, refetch: fetchData } = useQuery({
    queryKey: [...queryKeys.tracker(profileId), page, pageSize],
    queryFn: ({ signal }) => getTrackerData(profileId, pageSize, (page - 1) * pageSize, signal),
  });

  const rows = paginatedResult?.data ?? [];
  const totalCount = paginatedResult?.totalCount ?? 0;

  const error = queryError?.message ?? null;

  // Initialize edit state for a row on first interaction
  function getRowEdits(row: TrackerRow): RowEdits {
    if (edits[row.job_id]) return edits[row.job_id];
    return {
      method: row.app_method || "",
      platform: row.app_platform || "",
      response_type: row.response_type || "",
      notes: row.app_notes || "",
    };
  }

  function updateEdit(jobId: number, field: keyof RowEdits, value: string) {
    setEdits((prev) => {
      const row = rows.find((r) => r.job_id === jobId);
      const current = prev[jobId] || {
        method: row?.app_method || "",
        platform: row?.app_platform || "",
        response_type: row?.response_type || "",
        notes: row?.app_notes || "",
      };
      return { ...prev, [jobId]: { ...current, [field]: value } };
    });
  }

  const upsertMutation = useMutation({
    mutationFn: (data: { job_id: number; profile_id: number; method: string; platform: string; response_type: string | null; notes: string | null; app_id: number | null }) =>
      upsertApplication(data),
    onMutate: async (data) => {
      const queryKey = [...queryKeys.tracker(profileId), page, pageSize];
      await queryClient.cancelQueries({ queryKey });
      const prev = queryClient.getQueryData<PaginatedResult<TrackerRow[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<TrackerRow[]>>(queryKey, {
          ...prev,
          data: prev.data.map(r => r.job_id === data.job_id ? {
            ...r,
            app_method: data.method,
            app_platform: data.platform,
            response_type: data.response_type,
            app_notes: data.notes,
          } : r),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData([...queryKeys.tracker(profileId), page, pageSize], ctx.prev);
      }
    },
    onSuccess: (_data, vars) => {
      // Green flash
      setSavedRows((prev) => new Set(prev).add(vars.job_id));
      setTimeout(() => {
        setSavedRows((prev) => {
          const next = new Set(prev);
          next.delete(vars.job_id);
          return next;
        });
      }, 1500);
      // Clear edits for this row
      setEdits((prev) => {
        const next = { ...prev };
        delete next[vars.job_id];
        return next;
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker(profileId) });
    },
  });

  const obsoleteMutation = useMutation({
    mutationFn: (jobId: number) => markJobObsolete(jobId),
    onMutate: async (jobId) => {
      const queryKey = [...queryKeys.tracker(profileId), page, pageSize];
      await queryClient.cancelQueries({ queryKey });
      const prev = queryClient.getQueryData<PaginatedResult<TrackerRow[]>>(queryKey);
      if (prev) {
        queryClient.setQueryData<PaginatedResult<TrackerRow[]>>(queryKey, {
          ...prev,
          data: prev.data.map(r => r.job_id === jobId ? { ...r, is_obsolete: !r.is_obsolete } : r),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData([...queryKeys.tracker(profileId), page, pageSize], ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker(profileId) });
    },
  });

  const filteredRows = showObsolete
    ? rows
    : rows.filter((r) => !r.is_obsolete);

  return (
    <div>
      <PageHeader
        title="Application Tracker"
        subtitle="Spreadsheet-style management"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (filteredRows.length === 0) return;
            const rows = filteredRows.map((r) => ({
              Score: r.match_score,
              Decision: r.apply_decision,
              Company: r.company,
              Title: r.title,
              Source: r.source,
              Location: r.location ?? "",
              Remote: r.is_remote ? "Yes" : "No",
              Method: r.app_method ?? "",
              Platform: r.app_platform ?? "",
              "Applied At": r.applied_at ?? "",
              "Response Type": r.response_type ?? "",
              Notes: r.app_notes ?? "",
              URL: r.job_url ?? "",
            }));
            exportToExcel(rows, "tracker.xlsx", "Tracker");
          }}
        >
          Export Excel
        </Button>
      </PageHeader>

      {/* Error state */}
      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm text-red-700">{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchData()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Filter toggle */}
      <div className="mb-4 flex items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={showObsolete}
            onChange={(e) => setShowObsolete(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          Show obsolete jobs
        </label>
        <span className="text-xs text-muted-foreground">
          ({filteredRows.length} of {rows.length} jobs)
        </span>
      </div>

      {/* Loading state */}
      {loading && <TrackerSkeleton />}

      {/* Empty state */}
      {!loading && !error && filteredRows.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No actionable jobs found
            </p>
          </CardContent>
        </Card>
      )}

      {/* Data table */}
      {!loading && rows.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-primary text-white text-xs uppercase">
                  <tr>
                    <th className="px-3 py-2.5 text-left">Score</th>
                    <th className="px-3 py-2.5 text-left">Decision</th>
                    <th className="px-3 py-2.5 text-left">Company</th>
                    <th className="px-3 py-2.5 text-left">Title</th>
                    <th className="px-3 py-2.5 text-left">Source</th>
                    <th className="px-3 py-2.5 text-left">Method</th>
                    <th className="px-3 py-2.5 text-left">Platform</th>
                    <th className="px-3 py-2.5 text-left">Status</th>
                    <th className="px-3 py-2.5 text-left">Notes</th>
                    <th className="px-3 py-2.5 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredRows.map((row) => {
                    const edit = getRowEdits(row);
                    const isSaving = upsertMutation.isPending && upsertMutation.variables?.job_id === row.job_id;
                    const isSaved = savedRows.has(row.job_id);
                    const isObsolete = row.is_obsolete;

                    return (
                      <tr
                        key={row.job_id}
                        className={cn(
                          "hover:bg-gray-50 transition-colors",
                          isObsolete && "opacity-50",
                          isSaved && "bg-emerald-50",
                        )}
                      >
                        {/* Score */}
                        <td className="px-3 py-2.5">
                          <Badge
                            className={cn(
                              "text-xs text-white font-bold",
                              scoreBadgeColor(row.match_score),
                            )}
                          >
                            {row.match_score}
                          </Badge>
                        </td>

                        {/* Decision */}
                        <td className="px-3 py-2.5">
                          <Badge
                            className={cn(
                              "text-xs",
                              decisionColor(row.apply_decision),
                            )}
                          >
                            {row.apply_decision}
                          </Badge>
                        </td>

                        {/* Company */}
                        <td className="px-3 py-2.5 max-w-[160px]">
                          {row.job_url ? (
                            <a
                              href={row.job_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={cn(
                                "text-blue-600 hover:underline font-medium truncate block",
                                isObsolete && "line-through",
                              )}
                            >
                              {row.company}
                            </a>
                          ) : (
                            <span
                              className={cn(
                                "font-medium truncate block",
                                isObsolete && "line-through",
                              )}
                            >
                              {row.company}
                            </span>
                          )}
                        </td>

                        {/* Title */}
                        <td
                          className={cn(
                            "px-3 py-2.5 max-w-[200px] truncate",
                            isObsolete && "line-through",
                          )}
                        >
                          {row.title}
                        </td>

                        {/* Source */}
                        <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">
                          {row.source}
                        </td>

                        {/* Method (editable) */}
                        <td className="px-3 py-2.5">
                          <Select
                            value={edit.method || "__empty__"}
                            onValueChange={(val) =>
                              updateEdit(
                                row.job_id,
                                "method",
                                val === "__empty__" ? "" : val,
                              )
                            }
                          >
                            <SelectTrigger className="h-8 w-[140px] text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__empty__">&mdash;</SelectItem>
                              {APPLICATION_METHODS.map((m) => (
                                <SelectItem key={m} value={m}>
                                  {m}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>

                        {/* Platform (editable) */}
                        <td className="px-3 py-2.5">
                          <Input
                            className="h-8 w-[120px] text-xs"
                            value={edit.platform}
                            onChange={(e) =>
                              updateEdit(
                                row.job_id,
                                "platform",
                                e.target.value,
                              )
                            }
                            placeholder="Platform"
                          />
                        </td>

                        {/* Status / Response Type (editable) */}
                        <td className="px-3 py-2.5">
                          <Select
                            value={edit.response_type || "__empty__"}
                            onValueChange={(val) =>
                              updateEdit(
                                row.job_id,
                                "response_type",
                                val === "__empty__" ? "" : val,
                              )
                            }
                          >
                            <SelectTrigger className="h-8 w-[150px] text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__empty__">&mdash;</SelectItem>
                              {RESPONSE_TYPES.map((rt) => (
                                <SelectItem key={rt} value={rt}>
                                  {rt}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>

                        {/* Notes (editable) */}
                        <td className="px-3 py-2.5">
                          <Input
                            className="h-8 w-[160px] text-xs"
                            value={edit.notes}
                            onChange={(e) =>
                              updateEdit(row.job_id, "notes", e.target.value)
                            }
                            placeholder="Notes"
                          />
                        </td>

                        {/* Actions */}
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1">
                            <Button
                              variant="default"
                              size="sm"
                              className="h-7 text-xs"
                              disabled={!canEdit || isSaving}
                              onClick={() => {
                                const edit = getRowEdits(row);
                                upsertMutation.mutate({
                                  job_id: row.job_id,
                                  profile_id: profileId,
                                  method: edit.method || "",
                                  platform: edit.platform || "",
                                  response_type: edit.response_type || null,
                                  notes: edit.notes || null,
                                  app_id: row.app_id,
                                });
                              }}
                            >
                              {isSaving ? "Saving..." : "Save"}
                            </Button>
                            {!isObsolete && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs text-red-600 hover:text-red-700"
                                disabled={!canEdit}
                                onClick={() => obsoleteMutation.mutate(row.job_id)}
                              >
                                Obsolete
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {!loading && !error && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={totalCount}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}

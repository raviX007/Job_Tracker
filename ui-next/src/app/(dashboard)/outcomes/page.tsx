"use client";

import { useState, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  getApplicationsForUpdate,
  getAnalyzedJobsForUpdate,
  updateApplicationOutcome,
  createApplication,
} from "@/lib/api";
import { useProfile, isDemoMode } from "@/hooks/use-profile";
import { useAuth } from "@/hooks/use-auth";
import { queryKeys } from "@/lib/query-keys";
import { cn, scoreBadgeColor, formatDate, decisionColor } from "@/lib/utils";
import { RESPONSE_TYPES, APPLICATION_METHODS } from "@/lib/constants";
import { PageHeader } from "@/components/layout/page-header";
import type { ApplicationForUpdate, AnalyzedJobForUpdate } from "@/lib/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { SkeletonCard } from "@/components/ui/skeletons";

// ─── Loading skeletons ───────────────────────────────

function UpdateSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonCard key={i} lines={3} />
      ))}
    </div>
  );
}

function LogSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonCard key={i} lines={2} />
      ))}
    </div>
  );
}

// ─── Form state types ────────────────────────────────

interface OutcomeForm {
  response_type: string;
  response_date: string;
  notes: string;
}

interface LogForm {
  method: string;
  platform: string;
}

// ─── Page ────────────────────────────────────────────

export default function OutcomesPage() {
  const { profileId } = useProfile();
  const demo = isDemoMode();
  const { canEdit } = useAuth();
  const readOnly = demo || !canEdit;
  const queryClient = useQueryClient();

  // Form state
  const [outcomeForms, setOutcomeForms] = useState<Record<number, OutcomeForm>>({});
  const [savedAppId, setSavedAppId] = useState<number | null>(null);
  const [logForms, setLogForms] = useState<Record<number, LogForm>>({});
  const [loggedJobId, setLoggedJobId] = useState<number | null>(null);

  // ── Fetch applications for update ─────────────────

  const { data: applications = [], isLoading: loadingApps, error: errorAppsQ, refetch: refetchApps } = useQuery({
    queryKey: queryKeys.appsForUpdate(profileId),
    queryFn: ({ signal }) => getApplicationsForUpdate(profileId, signal),
  });

  const errorApps = errorAppsQ?.message ?? null;

  // Initialize form state when applications data changes
  useEffect(() => {
    if (applications.length > 0) {
      const forms: Record<number, OutcomeForm> = {};
      for (const app of applications) {
        forms[app.app_id] = {
          response_type: app.response_type ?? "",
          response_date: app.response_date ?? "",
          notes: app.notes ?? "",
        };
      }
      setOutcomeForms(forms);
    }
  }, [applications]);

  // ── Fetch analyzed jobs for log ───────────────────

  const { data: analyzedJobs = [], isLoading: loadingJobs, error: errorJobsQ, refetch: refetchJobs } = useQuery({
    queryKey: queryKeys.analyzedJobs(profileId),
    queryFn: ({ signal }) => getAnalyzedJobsForUpdate(profileId, signal),
  });

  const errorJobs = errorJobsQ?.message ?? null;

  // Initialize log form state when jobs data changes
  useEffect(() => {
    if (analyzedJobs.length > 0) {
      const forms: Record<number, LogForm> = {};
      for (const job of analyzedJobs) {
        forms[job.job_id] = {
          method: "",
          platform: "",
        };
      }
      setLogForms(forms);
    }
  }, [analyzedJobs]);

  // ── Update outcome form field ─────────────────────

  const updateOutcomeField = (appId: number, field: keyof OutcomeForm, value: string) => {
    setOutcomeForms((prev) => ({
      ...prev,
      [appId]: {
        ...prev[appId],
        [field]: value,
      },
    }));
  };

  // ── Update log form field ─────────────────────────

  const updateLogField = (jobId: number, field: keyof LogForm, value: string) => {
    setLogForms((prev) => ({
      ...prev,
      [jobId]: {
        ...prev[jobId],
        [field]: value,
      },
    }));
  };

  // ── Save outcome (optimistic) ─────────────────────

  const outcomeMutation = useMutation({
    mutationFn: ({ appId, data }: { appId: number; data: { response_type: string; response_date: string | null; notes: string } }) =>
      updateApplicationOutcome(appId, data),
    onMutate: async ({ appId, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.appsForUpdate(profileId) });
      const prev = queryClient.getQueryData<ApplicationForUpdate[]>(queryKeys.appsForUpdate(profileId));
      if (prev) {
        queryClient.setQueryData<ApplicationForUpdate[]>(
          queryKeys.appsForUpdate(profileId),
          prev.map(a => a.app_id === appId ? { ...a, response_type: data.response_type, response_date: data.response_date, notes: data.notes } : a),
        );
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKeys.appsForUpdate(profileId), ctx.prev);
    },
    onSuccess: (_data, { appId }) => {
      setSavedAppId(appId);
      setTimeout(() => setSavedAppId(null), 2000);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appsForUpdate(profileId) });
    },
  });

  // ── Log new application (optimistic) ──────────────

  const logMutation = useMutation({
    mutationFn: (data: { job_id: number; profile_id: number; method: string; platform: string }) =>
      createApplication(data),
    onMutate: async (data) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.analyzedJobs(profileId) });
      const prev = queryClient.getQueryData<AnalyzedJobForUpdate[]>(queryKeys.analyzedJobs(profileId));
      if (prev) {
        // Optimistically remove the job from the list
        queryClient.setQueryData<AnalyzedJobForUpdate[]>(
          queryKeys.analyzedJobs(profileId),
          prev.filter(j => j.job_id !== data.job_id),
        );
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(queryKeys.analyzedJobs(profileId), ctx.prev);
    },
    onSuccess: (_data, { job_id }) => {
      setLoggedJobId(job_id);
      setTimeout(() => setLoggedJobId(null), 2000);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appsForUpdate(profileId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.analyzedJobs(profileId) });
    },
  });

  // ── Demo mode early return ────────────────────────

  if (demo) {
    return (
      <div>
        <PageHeader title="Update Outcomes" subtitle="Track application responses" />
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="py-6">
            <p className="text-sm text-blue-700">
              Outcome updates are disabled in demo mode. Switch to a live profile to update
              application outcomes and log new applications.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────

  return (
    <div>
      <PageHeader title="Update Outcomes" subtitle="Track application responses" />

      <Tabs defaultValue="update" className="space-y-4">
        <TabsList>
          <TabsTrigger value="update">Update Existing</TabsTrigger>
          <TabsTrigger value="log">Log New Application</TabsTrigger>
        </TabsList>

        {/* ════════ Update Existing Tab ════════ */}
        <TabsContent value="update" className="space-y-4">
          {/* Error */}
          {errorApps && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="flex items-center justify-between py-4">
                <p className="text-sm text-red-700">{errorApps}</p>
                <Button variant="outline" size="sm" onClick={() => refetchApps()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Loading */}
          {loadingApps && <UpdateSkeleton />}

          {/* Empty */}
          {!loadingApps && applications.length === 0 && !errorApps && (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No applications to update. Log some applications first.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Application cards */}
          {!loadingApps &&
            applications.map((app) => {
              const form = outcomeForms[app.app_id];
              const isSaving = outcomeMutation.isPending && outcomeMutation.variables?.appId === app.app_id;
              const isSaved = savedAppId === app.app_id;

              return (
                <Card key={app.app_id} className="hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-base">{app.company}</CardTitle>
                      <div
                        className={cn(
                          "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white",
                          scoreBadgeColor(app.match_score),
                        )}
                      >
                        {app.match_score}
                      </div>
                      {app.response_type && (
                        <Badge variant="outline" className="text-xs">
                          {app.response_type}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">{app.title}</p>
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>Method: {app.method}</span>
                      {app.platform && <span>Platform: {app.platform}</span>}
                      <span>Applied: {formatDate(app.applied_at)}</span>
                    </div>
                  </CardHeader>

                  <CardContent>
                    {form && (
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {/* Response Type */}
                        <div>
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Response Type
                          </label>
                          <Select
                            value={form.response_type}
                            onValueChange={(val) =>
                              updateOutcomeField(app.app_id, "response_type", val === "__none__" ? "" : val)
                            }
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="None" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__none__">None</SelectItem>
                              {RESPONSE_TYPES.map((rt) => (
                                <SelectItem key={rt} value={rt}>
                                  {rt}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Response Date */}
                        <div>
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Response Date
                          </label>
                          <Input
                            type="date"
                            value={form.response_date}
                            onChange={(e) =>
                              updateOutcomeField(app.app_id, "response_date", e.target.value)
                            }
                          />
                        </div>

                        {/* Notes */}
                        <div className="sm:col-span-2 lg:col-span-1">
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Notes
                          </label>
                          <Textarea
                            value={form.notes}
                            onChange={(e) =>
                              updateOutcomeField(app.app_id, "notes", e.target.value)
                            }
                            rows={2}
                            placeholder="Any notes..."
                          />
                        </div>

                        {/* Save */}
                        <div className="flex items-end">
                          <Button
                            size="sm"
                            onClick={() => {
                              const form = outcomeForms[app.app_id];
                              if (!form) return;
                              outcomeMutation.mutate({
                                appId: app.app_id,
                                data: { response_type: form.response_type, response_date: form.response_date || null, notes: form.notes },
                              });
                            }}
                            disabled={readOnly || isSaving}
                            className="w-full sm:w-auto"
                          >
                            {isSaving
                              ? "Saving..."
                              : isSaved
                                ? "Saved!"
                                : "Save"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
        </TabsContent>

        {/* ════════ Log New Application Tab ════════ */}
        <TabsContent value="log" className="space-y-4">
          {/* Error */}
          {errorJobs && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="flex items-center justify-between py-4">
                <p className="text-sm text-red-700">{errorJobs}</p>
                <Button variant="outline" size="sm" onClick={() => refetchJobs()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Loading */}
          {loadingJobs && <LogSkeleton />}

          {/* Empty */}
          {!loadingJobs && analyzedJobs.length === 0 && !errorJobs && (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No eligible analyzed jobs to log. Run the pipeline to analyze more jobs.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Job cards */}
          {!loadingJobs &&
            analyzedJobs.map((job) => {
              const form = logForms[job.job_id];
              const isLogging = logMutation.isPending && logMutation.variables?.job_id === job.job_id;
              const isLogged = loggedJobId === job.job_id;

              return (
                <Card key={job.job_id} className="hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-base">{job.company}</CardTitle>
                      <div
                        className={cn(
                          "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white",
                          scoreBadgeColor(job.match_score),
                        )}
                      >
                        {job.match_score}
                      </div>
                      <Badge className={cn("text-xs", decisionColor(job.apply_decision))}>
                        {job.apply_decision}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{job.title}</p>
                  </CardHeader>

                  <CardContent>
                    {form && (
                      <div className="flex flex-wrap items-end gap-3">
                        {/* Method */}
                        <div className="w-48">
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Method
                          </label>
                          <Select
                            value={form.method}
                            onValueChange={(val) => updateLogField(job.job_id, "method", val)}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select method" />
                            </SelectTrigger>
                            <SelectContent>
                              {APPLICATION_METHODS.map((m) => (
                                <SelectItem key={m} value={m}>
                                  {m}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Platform */}
                        <div className="w-48">
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Platform
                          </label>
                          <Input
                            value={form.platform}
                            onChange={(e) =>
                              updateLogField(job.job_id, "platform", e.target.value)
                            }
                            placeholder="e.g. LinkedIn, Company Site"
                          />
                        </div>

                        {/* Log button */}
                        <Button
                          size="sm"
                          onClick={() => {
                            const form = logForms[job.job_id];
                            if (!form || !form.method) return;
                            logMutation.mutate({
                              job_id: job.job_id,
                              profile_id: profileId,
                              method: form.method,
                              platform: form.platform,
                            });
                          }}
                          disabled={readOnly || isLogging || !form.method}
                        >
                          {isLogging
                            ? "Logging..."
                            : isLogged
                              ? "Logged!"
                              : "Log Application"}
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
        </TabsContent>
      </Tabs>
    </div>
  );
}

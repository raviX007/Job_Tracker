"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getApplications, getSources } from "@/lib/api";
import { useProfile } from "@/hooks/use-profile";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { queryKeys } from "@/lib/query-keys";
import {
  cn,
  scoreBadgeColor,
  decisionColor,
  formatDate,
} from "@/lib/utils";
import { DECISIONS } from "@/lib/constants";
import { exportToExcel } from "@/lib/export";
import { PageHeader } from "@/components/layout/page-header";
import type { Application, ApplicationFilters } from "@/lib/types";

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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/pagination";
import { SkeletonGrid } from "@/components/ui/skeletons";

// ─── Loading skeleton ────────────────────────────────

function ApplicationsSkeleton() {
  return <SkeletonGrid count={6} cardProps={{ avatar: true, lines: 1, header: false }} />;
}

// ─── Application card ────────────────────────────────

function ApplicationCard({ app }: { app: Application }) {
  const [expanded, setExpanded] = useState(false);

  const matchedSlice = app.skills_matched?.slice(0, 5) ?? [];
  const missingSlice = app.skills_missing?.slice(0, 5) ?? [];
  const hasMoreMatched = (app.skills_matched?.length ?? 0) > 5;
  const hasMoreMissing = (app.skills_missing?.length ?? 0) > 5;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="pt-6">
        {/* Header row */}
        <div className="flex items-start gap-3">
          {/* Score circle */}
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
              scoreBadgeColor(app.match_score),
            )}
          >
            {app.match_score}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate font-semibold text-gray-900">
                {app.company}
              </p>
              <Badge
                className={cn("shrink-0 text-xs", decisionColor(app.apply_decision))}
              >
                {app.apply_decision}
              </Badge>
            </div>
            <p className="mt-0.5 truncate text-sm text-muted-foreground">
              {app.title}
            </p>
          </div>

          {/* External link */}
          {app.job_url && (
            <a
              href={app.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-muted-foreground hover:text-blue-600"
              title="Open job posting"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          )}
        </div>

        {/* Meta row */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{app.source}</span>
          {app.location && <span>{app.location}</span>}
          {app.is_remote && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              Remote
            </Badge>
          )}
          {app.date_posted && <span>{formatDate(app.date_posted)}</span>}
        </div>

        {/* Skills */}
        {(matchedSlice.length > 0 || missingSlice.length > 0) && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {matchedSlice.map((s) => (
              <Badge
                key={s}
                variant="secondary"
                className="border border-emerald-200 bg-emerald-50 text-emerald-700 text-[10px]"
              >
                {s}
              </Badge>
            ))}
            {hasMoreMatched && (
              <span className="text-[10px] text-emerald-600">
                +{app.skills_matched.length - 5} more
              </span>
            )}
            {missingSlice.map((s) => (
              <Badge
                key={s}
                variant="secondary"
                className="border border-red-200 bg-red-50 text-red-700 text-[10px]"
              >
                {s}
              </Badge>
            ))}
            {hasMoreMissing && (
              <span className="text-[10px] text-red-600">
                +{app.skills_missing.length - 5} more
              </span>
            )}
          </div>
        )}

        {/* Collapsible details */}
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-medium text-blue-600 hover:underline"
          >
            {expanded ? "Hide Details" : "Details"}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3 rounded-md border bg-gray-50/50 p-3 text-xs text-gray-700">
              {app.ats_keywords && app.ats_keywords.length > 0 && (
                <div>
                  <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
                    ATS Keywords
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {app.ats_keywords.map((kw) => (
                      <Badge key={kw} variant="outline" className="text-[10px]">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {app.company_type && (
                <div>
                  <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
                    Company Type
                  </p>
                  <p>{app.company_type}</p>
                </div>
              )}

              {app.experience_required && (
                <div>
                  <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
                    Experience Required
                  </p>
                  <p>{app.experience_required}</p>
                </div>
              )}

              {app.cold_email_angle && (
                <div>
                  <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
                    Cold Email Angle
                  </p>
                  <p className="whitespace-pre-wrap">{app.cold_email_angle}</p>
                </div>
              )}

              {app.cover_letter && (
                <div>
                  <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
                    Cover Letter
                  </p>
                  <p className="whitespace-pre-wrap">{app.cover_letter}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Table view ──────────────────────────────────────

function ApplicationsTable({ apps }: { apps: Application[] }) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Decision</th>
            <th className="px-4 py-3">Company</th>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Date</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app) => (
            <tr
              key={app.job_id}
              className="border-b last:border-0 hover:bg-gray-50/60"
            >
              <td className="px-4 py-3">
                <span
                  className={cn(
                    "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white",
                    scoreBadgeColor(app.match_score),
                  )}
                >
                  {app.match_score}
                </span>
              </td>
              <td className="px-4 py-3">
                <Badge
                  className={cn("text-xs", decisionColor(app.apply_decision))}
                >
                  {app.apply_decision}
                </Badge>
              </td>
              <td className="px-4 py-3 font-medium">
                {app.job_url ? (
                  <a
                    href={app.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {app.company}
                  </a>
                ) : (
                  app.company
                )}
              </td>
              <td className="max-w-[240px] truncate px-4 py-3 text-muted-foreground">
                {app.title}
              </td>
              <td className="px-4 py-3 text-muted-foreground">{app.source}</td>
              <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                {formatDate(app.date_posted)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────

export default function ApplicationsPage() {
  const { profileId } = useProfile();

  // Filter state
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(100);
  const [decision, setDecision] = useState("All");
  const [source, setSource] = useState("All");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 400);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  // View
  const [view, setView] = useState<string>("cards");

  // Fetch sources
  const { data: sources = [] } = useQuery({
    queryKey: queryKeys.sources(profileId),
    queryFn: async ({ signal }) => {
      const data = await getSources(profileId, signal);
      return data.filter((s) => s !== "All");
    },
  });

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [minScore, maxScore, decision, source, debouncedSearch]);

  // Fetch applications when filters change
  const currentFilters: Partial<ApplicationFilters> = {
    min_score: minScore,
    max_score: maxScore,
    decision,
    source,
    search: debouncedSearch,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  };

  const { data: paginatedResult, isLoading: loading, error: queryError, refetch: fetchApplications } = useQuery({
    queryKey: queryKeys.applications(profileId, currentFilters),
    queryFn: ({ signal }) => getApplications(profileId, currentFilters, signal),
  });

  const applications = paginatedResult?.data ?? [];
  const totalCount = paginatedResult?.totalCount ?? 0;
  const error = queryError?.message ?? null;

  const handleExport = () => {
    if (applications.length === 0) return;
    const rows = applications.map((a) => ({
      Score: a.match_score,
      Decision: a.apply_decision,
      Company: a.company,
      Title: a.title,
      Source: a.source,
      Location: a.location ?? "",
      Remote: a.is_remote ? "Yes" : "No",
      "Date Posted": a.date_posted ?? "",
      "Skills Matched": a.skills_matched?.join(", ") ?? "",
      "Skills Missing": a.skills_missing?.join(", ") ?? "",
      "Company Type": a.company_type ?? "",
      Route: a.route_action ?? "",
      URL: a.job_url ?? "",
    }));
    exportToExcel(rows, "applications.xlsx", "Applications");
  };

  return (
    <div>
      <PageHeader title="Applications" subtitle="Browse analyzed job matches">
        <Button variant="outline" size="sm" onClick={handleExport}>
          Export Excel
        </Button>
      </PageHeader>

      {/* ── Filter bar ──────────────────────────────── */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-end gap-4">
            {/* Score range */}
            <div className="flex items-end gap-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Min Score
                </label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(e) =>
                    setMinScore(Math.max(0, Math.min(100, Number(e.target.value))))
                  }
                  className="w-20"
                />
              </div>
              <span className="mb-2 text-sm text-muted-foreground">-</span>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Max Score
                </label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={maxScore}
                  onChange={(e) =>
                    setMaxScore(Math.max(0, Math.min(100, Number(e.target.value))))
                  }
                  className="w-20"
                />
              </div>
            </div>

            {/* Decision */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Decision
              </label>
              <Select value={decision} onValueChange={setDecision}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DECISIONS.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Source */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Source
              </label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All</SelectItem>
                  {sources.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Search
              </label>
              <Input
                placeholder="Search company, title, skills..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Error state ─────────────────────────────── */}
      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm text-red-700">{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchApplications()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── Results count ───────────────────────────── */}
      {!loading && !error && (
        <p className="mb-4 text-sm text-muted-foreground">
          {totalCount.toLocaleString()} application{totalCount !== 1 ? "s" : ""}{" "}
          found
        </p>
      )}

      {/* ── View toggle + content ───────────────────── */}
      <Tabs value={view} onValueChange={setView}>
        <TabsList className="mb-4">
          <TabsTrigger value="cards">Cards</TabsTrigger>
          <TabsTrigger value="table">Table</TabsTrigger>
        </TabsList>

        {/* Loading */}
        {loading && (
          <div className="mt-4">
            <ApplicationsSkeleton />
          </div>
        )}

        {/* Empty */}
        {!loading && !error && applications.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-muted-foreground">No applications found.</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Try adjusting your filters or wait for the pipeline to analyze
                new jobs.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Cards view */}
        {!loading && !error && applications.length > 0 && (
          <>
            <TabsContent value="cards" className="mt-0">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {applications.map((app) => (
                  <ApplicationCard key={app.job_id} app={app} />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="table" className="mt-0">
              <ApplicationsTable apps={applications} />
            </TabsContent>
          </>
        )}
      </Tabs>

      {/* ── Pagination ──────────────────────────────── */}
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

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getStartupProfiles,
  getStartupProfileStats,
  getStartupProfileSources,
} from "@/lib/api";
import { useProfile } from "@/hooks/use-profile";
import { queryKeys } from "@/lib/query-keys";
import { cn, scoreBadgeColor, formatDate } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";
import type {
  StartupProfile,
  StartupProfileFilters,
} from "@/lib/types";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
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
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Pagination } from "@/components/ui/pagination";
import { SkeletonKpiRow, SkeletonGrid } from "@/components/ui/skeletons";

// ─── Loading skeleton ────────────────────────────────

function StartupsSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonKpiRow count={4} />
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-40" />
            ))}
          </div>
        </CardContent>
      </Card>
      <SkeletonGrid count={3} columns="grid-cols-1" cardProps={{ header: false, lines: 4 }} />
    </div>
  );
}

// ─── Page ────────────────────────────────────────────

export default function StartupsPage() {
  const { profileId } = useProfile();
  // Filters
  const [filters, setFilters] = useState<Partial<StartupProfileFilters>>({
    source: "All",
    funding_round: "All",
    min_age: 0,
    max_age: 24,
    has_funding: "All",
    search: "",
    sort_by: "match_score",
    limit: 50,
    offset: 0,
  });
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const currentFilters = {
    ...filters,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  };

  const { data: queryData, isLoading: loading, error: queryError, refetch: fetchData } = useQuery({
    queryKey: queryKeys.startups(profileId, currentFilters as Record<string, unknown>),
    queryFn: async ({ signal }) => {
      const [profileResult, statsData, sourcesData] = await Promise.all([
        getStartupProfiles(profileId, currentFilters, signal),
        getStartupProfileStats(profileId, signal),
        getStartupProfileSources(profileId, signal),
      ]);
      return {
        startups: profileResult.data,
        totalCount: profileResult.totalCount,
        stats: statsData,
        sources: sourcesData,
      };
    },
  });

  const startups = queryData?.startups ?? [];
  const totalCount = queryData?.totalCount ?? 0;
  const stats = queryData?.stats ?? null;
  const sources = queryData?.sources ?? [];
  const error = queryError?.message ?? null;

  function updateFilter<K extends keyof StartupProfileFilters>(
    key: K,
    value: StartupProfileFilters[K],
  ) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }

  // Derive funding round options from stats
  const fundingRoundOptions = stats?.by_funding
    ? Object.keys(stats.by_funding)
    : [];

  // Derive top source from stats
  const topSourceCount = stats?.by_source
    ? Math.max(...Object.values(stats.by_source), 0)
    : 0;

  // Derive funded count from stats
  const fundedCount = stats?.by_funding
    ? Object.values(stats.by_funding).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div>
      <PageHeader
        title="Startup Scout"
        subtitle="Discover early-stage startups"
      />

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

      {/* Loading state */}
      {loading && <StartupsSkeleton />}

      {/* Loaded content */}
      {!loading && stats && (
        <div className="space-y-6">
          {/* ── Stats Summary ──────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Startups
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {stats.total.toLocaleString()}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Avg Completeness
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {Math.round(stats.avg_completeness)}%
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Top Source Count
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {topSourceCount.toLocaleString()}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Funded
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {fundedCount.toLocaleString()}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* ── Filter Bar ─────────────────────────────── */}
          <Card>
            <CardContent className="py-4">
              <div className="flex flex-wrap items-end gap-3">
                {/* Source */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Source
                  </label>
                  <Select
                    value={filters.source || "All"}
                    onValueChange={(val) => updateFilter("source", val)}
                  >
                    <SelectTrigger className="h-9 w-[160px] text-sm">
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

                {/* Funding Round */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Funding Round
                  </label>
                  <Select
                    value={filters.funding_round || "All"}
                    onValueChange={(val) => updateFilter("funding_round", val)}
                  >
                    <SelectTrigger className="h-9 w-[160px] text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="All">All</SelectItem>
                      {fundingRoundOptions.map((fr) => (
                        <SelectItem key={fr} value={fr}>
                          {fr}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Min Age */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Min Age (mo)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    max={24}
                    className="h-9 w-[90px] text-sm"
                    value={filters.min_age ?? 0}
                    onChange={(e) =>
                      updateFilter("min_age", parseInt(e.target.value) || 0)
                    }
                  />
                </div>

                {/* Max Age */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Max Age (mo)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    max={24}
                    className="h-9 w-[90px] text-sm"
                    value={filters.max_age ?? 24}
                    onChange={(e) =>
                      updateFilter("max_age", parseInt(e.target.value) || 24)
                    }
                  />
                </div>

                {/* Search */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Search
                  </label>
                  <Input
                    className="h-9 w-[200px] text-sm"
                    placeholder="Search startups..."
                    value={filters.search || ""}
                    onChange={(e) => updateFilter("search", e.target.value)}
                  />
                </div>

                {/* Sort By */}
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Sort By
                  </label>
                  <Select
                    value={filters.sort_by || "match_score"}
                    onValueChange={(val) => updateFilter("sort_by", val)}
                  >
                    <SelectTrigger className="h-9 w-[170px] text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="match_score">Match Score</SelectItem>
                      <SelectItem value="founding_date">
                        Founding Date
                      </SelectItem>
                      <SelectItem value="data_completeness">
                        Completeness
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ── Startup Cards ──────────────────────────── */}
          {startups.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No startup profiles found
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {startups.map((startup) => (
                <StartupCard key={startup.id} startup={startup} />
              ))}
            </div>
          )}

          {/* ── Pagination ──────────────────────────── */}
          <Pagination
            page={page}
            pageSize={pageSize}
            total={totalCount}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  );
}

// ─── Startup Card ────────────────────────────────────

function StartupCard({ startup }: { startup: StartupProfile }) {
  const hasColdEmail = startup.cold_email_id != null;

  const profileContent = (
    <div className="space-y-4">
      {/* One-liner */}
      {startup.one_liner && (
        <p className="text-sm text-muted-foreground">{startup.one_liner}</p>
      )}

      {/* Info grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <div>
          <span className="text-muted-foreground">Founded:</span>{" "}
          <span className="font-medium">{formatDate(startup.founding_date)}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Age:</span>{" "}
          <span className="font-medium">
            {startup.age_months != null ? `${startup.age_months} months` : "--"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Employees:</span>{" "}
          <span className="font-medium">
            {startup.employee_count ?? "--"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Funding:</span>{" "}
          <span className="font-medium">
            {startup.funding_amount
              ? `${startup.funding_amount} (${startup.funding_round || "N/A"})`
              : "--"}
          </span>
        </div>
        <div className="col-span-2">
          <span className="text-muted-foreground">Completeness:</span>
          <div className="mt-1 flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-primary transition-all"
                style={{
                  width: `${Math.min(startup.data_completeness ?? 0, 100)}%`,
                }}
              />
            </div>
            <span className="text-xs font-medium">
              {Math.round(startup.data_completeness ?? 0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Founders */}
      {startup.founder_names.length > 0 && (
        <>
          <Separator />
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Founders
            </p>
            <div className="space-y-1">
              {startup.founder_names.map((name, i) => (
                <div key={i} className="text-sm">
                  <span className="font-medium">{name}</span>
                  {startup.founder_roles[i] && (
                    <span className="text-muted-foreground">
                      {" "}
                      &middot; {startup.founder_roles[i]}
                    </span>
                  )}
                  {startup.founder_emails[i] && (
                    <span className="text-muted-foreground">
                      {" "}
                      &middot;{" "}
                      <a
                        href={`mailto:${startup.founder_emails[i]}`}
                        className="text-blue-600 hover:underline"
                      >
                        {startup.founder_emails[i]}
                      </a>
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Tech Stack */}
      {startup.tech_stack.length > 0 && (
        <>
          <Separator />
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Tech Stack
            </p>
            <div className="flex flex-wrap gap-1.5">
              {startup.tech_stack.map((tech) => (
                <Badge key={tech} variant="default" className="text-xs">
                  {tech}
                </Badge>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Topics */}
      {startup.topics.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Topics
          </p>
          <div className="flex flex-wrap gap-1.5">
            {startup.topics.map((topic) => (
              <Badge key={topic} variant="secondary" className="text-xs">
                {topic}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Links row */}
      <Separator />
      <div className="flex flex-wrap gap-2">
        {startup.website_url && (
          <Button variant="outline" size="sm" className="h-7 text-xs" asChild>
            <a
              href={startup.website_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Website
            </a>
          </Button>
        )}
        {startup.yc_url && (
          <Button variant="outline" size="sm" className="h-7 text-xs" asChild>
            <a
              href={startup.yc_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              YC Profile
            </a>
          </Button>
        )}
        {startup.ph_url && (
          <Button variant="outline" size="sm" className="h-7 text-xs" asChild>
            <a
              href={startup.ph_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              ProductHunt
            </a>
          </Button>
        )}
        {startup.job_url && (
          <Button variant="outline" size="sm" className="h-7 text-xs" asChild>
            <a
              href={startup.job_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Job Listing
            </a>
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            {startup.website_url ? (
              <a
                href={startup.website_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-bold text-blue-600 hover:underline truncate"
              >
                {startup.startup_name}
              </a>
            ) : (
              <CardTitle className="text-lg truncate">
                {startup.startup_name}
              </CardTitle>
            )}
            <Badge variant="outline" className="shrink-0 text-xs">
              {startup.source}
            </Badge>
            {startup.match_score != null && (
              <Badge
                className={cn(
                  "shrink-0 text-xs text-white font-bold",
                  scoreBadgeColor(startup.match_score),
                )}
              >
                {startup.match_score}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {hasColdEmail ? (
          <Tabs defaultValue="profile">
            <TabsList className="mb-4">
              <TabsTrigger value="profile">Profile</TabsTrigger>
              <TabsTrigger value="cold-email">Cold Email</TabsTrigger>
            </TabsList>
            <TabsContent value="profile">{profileContent}</TabsContent>
            <TabsContent value="cold-email">
              <div className="space-y-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                    Subject
                  </p>
                  <p className="font-bold text-sm">
                    {startup.cold_email_subject}
                  </p>
                </div>
                <Separator />
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                    Body
                  </p>
                  <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                    {startup.cold_email_body}
                  </p>
                </div>
                {startup.cold_email_status && (
                  <div className="pt-2">
                    <Badge variant="outline" className="text-xs">
                      {startup.cold_email_status}
                    </Badge>
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        ) : (
          profileContent
        )}
      </CardContent>
    </Card>
  );
}

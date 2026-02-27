"use client";

import { useQuery } from "@tanstack/react-query";
import { getOverviewStats, getDailyTrends, getApplications } from "@/lib/api";
import { useProfile } from "@/hooks/use-profile";
import { queryKeys } from "@/lib/query-keys";
import { cn, scoreBadgeColor, decisionColor } from "@/lib/utils";
import { CHART_COLORS } from "@/lib/constants";
import { PageHeader, SectionHeader } from "@/components/layout/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonKpiRow, SkeletonChart, SkeletonGrid } from "@/components/ui/skeletons";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ─── Loading skeleton ────────────────────────────────

function OverviewSkeleton() {
  return (
    <div className="space-y-8">
      <SkeletonKpiRow count={4} />
      <SkeletonKpiRow count={6} columns="grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" />
      <SkeletonChart height="h-48" showTitle={false} />
      <SkeletonGrid count={4} cardProps={{ header: false, lines: 2 }} />
    </div>
  );
}

// ─── KPI card ────────────────────────────────────────

function KpiCard({
  label,
  value,
  borderColor,
}: {
  label: string;
  value: number;
  borderColor: string;
}) {
  return (
    <Card className={cn("border-t-4", borderColor)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold">{value.toLocaleString()}</p>
      </CardContent>
    </Card>
  );
}

// ─── Page ────────────────────────────────────────────

export default function OverviewPage() {
  const { profileId } = useProfile();

  const { data: queryData, isLoading: loading, error: queryError, refetch } = useQuery({
    queryKey: queryKeys.overview(profileId),
    queryFn: async ({ signal }) => {
      const [stats, trendData, topResult] = await Promise.all([
        getOverviewStats(profileId, signal),
        getDailyTrends(profileId, 7, signal),
        getApplications(profileId, {
          min_score: 70,
          max_score: 100,
          decision: "YES",
          limit: 6,
        }, signal),
      ]);
      return { stats, trends: trendData, topMatches: topResult.data };
    },
  });

  const data = queryData?.stats ?? null;
  const trends = queryData?.trends ?? [];
  const topMatches = queryData?.topMatches ?? [];
  const error = queryError?.message ?? null;

  return (
    <div>
      <PageHeader title="Overview" subtitle="Real-time dashboard" />

      {/* Error state */}
      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm text-red-700">{error}</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {loading && <OverviewSkeleton />}

      {/* Loaded content */}
      {!loading && data && (
        <div className="space-y-8">
          {/* ── Today's Activity ─────────────────────── */}
          <SectionHeader title="Today's Activity" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="Jobs Scraped"
              value={data.today_jobs}
              borderColor="border-t-[#00d4aa]"
            />
            <KpiCard
              label="Jobs Analyzed"
              value={data.today_analyzed}
              borderColor="border-t-[#1e3a5f]"
            />
            <KpiCard
              label="Emails Queued"
              value={data.today_emails}
              borderColor="border-t-[#f5a623]"
            />
            <KpiCard
              label="Applications"
              value={data.today_applied}
              borderColor="border-t-[#8e44ad]"
            />
          </div>

          {/* ── All-Time Summary ─────────────────────── */}
          <SectionHeader title="All-Time Summary" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { label: "Total Jobs", value: data.total_jobs },
              { label: "Analyzed", value: data.total_analyzed },
              { label: "Avg Score", value: Math.round(data.avg_score) },
              { label: "YES", value: data.total_yes },
              { label: "Emails", value: data.total_emails },
              { label: "This Week", value: data.week_jobs },
            ].map((item) => (
              <Card key={item.label}>
                <CardContent className="pt-6 text-center">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {item.label}
                  </p>
                  <p className="mt-1 text-2xl font-bold">
                    {item.value.toLocaleString()}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* ── 7-Day Trend ──────────────────────────── */}
          <SectionHeader title="7-Day Trend" />
          <Card>
            <CardContent className="pt-6">
              {trends.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No trend data available yet.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={trends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      tickFormatter={(v: string) =>
                        new Date(v).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                        })
                      }
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip
                      labelFormatter={(v: string) =>
                        new Date(v).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })
                      }
                    />
                    <Area
                      type="monotone"
                      dataKey="jobs_scraped"
                      name="Jobs Scraped"
                      stroke={CHART_COLORS[0]}
                      fill={CHART_COLORS[0]}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="jobs_analyzed"
                      name="Analyzed"
                      stroke={CHART_COLORS[1]}
                      fill={CHART_COLORS[1]}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* ── Top Matches ──────────────────────────── */}
          <SectionHeader title="Top Matches" />
          {topMatches.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No top matches yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {topMatches.map((match) => (
                <Card key={match.job_id} className="hover:shadow-md transition-shadow">
                  <CardContent className="flex items-start gap-4 pt-6">
                    {/* Score badge */}
                    <div
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white",
                        scoreBadgeColor(match.match_score),
                      )}
                    >
                      {match.match_score}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-semibold text-gray-900">
                          {match.company}
                        </p>
                        <Badge
                          className={cn(
                            "shrink-0 text-xs",
                            decisionColor(match.apply_decision),
                          )}
                        >
                          {match.apply_decision}
                        </Badge>
                      </div>
                      <p className="mt-0.5 truncate text-sm text-muted-foreground">
                        {match.title}
                      </p>
                      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{match.source}</span>
                        {match.job_url && (
                          <a
                            href={match.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                          >
                            View Job
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="12"
                              height="12"
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
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

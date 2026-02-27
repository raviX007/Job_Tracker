"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getDailyTrends,
  getScoreDistribution,
  getSourceBreakdown,
  getCompanyTypes,
  getResponseRates,
  getRouteBreakdown,
} from "@/lib/api";
import { useProfile } from "@/hooks/use-profile";
import { queryKeys } from "@/lib/query-keys";
import { formatDate } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SkeletonChart } from "@/components/ui/skeletons";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Area,
  AreaChart,
} from "recharts";

const COLORS = ["#00d4aa", "#1e3a5f", "#f5a623", "#e74c3c", "#8e44ad", "#3498db"];

function formatShortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

function renderPercentLabel({
  name,
  percent,
}: {
  name: string;
  percent: number;
}) {
  return `${name} ${(percent * 100).toFixed(0)}%`;
}

export default function AnalyticsPage() {
  const { profileId } = useProfile();

  const { data: queryData, isLoading: loading, error: queryError } = useQuery({
    queryKey: queryKeys.analytics(profileId),
    queryFn: async ({ signal }) => {
      const [trends, scores, sources, companies, responses, routes] =
        await Promise.all([
          getDailyTrends(profileId, 30, signal),
          getScoreDistribution(profileId, signal),
          getSourceBreakdown(profileId, signal),
          getCompanyTypes(profileId, signal),
          getResponseRates(profileId, signal),
          getRouteBreakdown(profileId, signal),
        ]);
      return {
        dailyTrends: trends,
        scoreDistribution: scores,
        sourceBreakdown: sources,
        companyTypes: companies,
        responseRates: responses,
        routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),
      };
    },
  });

  const dailyTrends = queryData?.dailyTrends ?? [];
  const scoreDistribution = queryData?.scoreDistribution ?? [];
  const sourceBreakdown = queryData?.sourceBreakdown ?? [];
  const companyTypes = queryData?.companyTypes ?? [];
  const responseRates = queryData?.responseRates ?? [];
  const routeBreakdown = queryData?.routeBreakdown ?? [];
  const error = queryError?.message ?? null;

  if (loading) {
    return (
      <div>
        <PageHeader title="Analytics" subtitle="Performance charts and trends" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonChart key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Analytics" subtitle="Performance charts and trends" />
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-red-600">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Performance charts and trends" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {/* 1. Daily Activity Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Activity Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={dailyTrends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  tick={{ fontSize: 11 }}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  labelFormatter={(label) => formatDate(label as string)}
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="jobs_scraped"
                  stackId="1"
                  stroke={COLORS[0]}
                  fill={COLORS[0]}
                  fillOpacity={0.6}
                  name="Jobs Scraped"
                />
                <Area
                  type="monotone"
                  dataKey="jobs_analyzed"
                  stackId="1"
                  stroke={COLORS[1]}
                  fill={COLORS[1]}
                  fillOpacity={0.6}
                  name="Jobs Analyzed"
                />
                <Area
                  type="monotone"
                  dataKey="emails_queued"
                  stackId="1"
                  stroke={COLORS[2]}
                  fill={COLORS[2]}
                  fillOpacity={0.6}
                  name="Emails Queued"
                />
                <Legend />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 2. Score Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={scoreDistribution}
                  dataKey="count"
                  nameKey="bracket"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  label={renderPercentLabel}
                >
                  {scoreDistribution.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 3. Source Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Source Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={sourceBreakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="source"
                  tick={{ fontSize: 11 }}
                  width={100}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Bar
                  dataKey="count"
                  fill={COLORS[0]}
                  radius={[0, 4, 4, 0]}
                  name="Total Jobs"
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 4. Company Types */}
        <Card>
          <CardHeader>
            <CardTitle>Company Types</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={companyTypes} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="company_type"
                  tick={{ fontSize: 11 }}
                  width={100}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Bar
                  dataKey="count"
                  fill={COLORS[1]}
                  radius={[0, 4, 4, 0]}
                  name="Total"
                />
                <Bar
                  dataKey="gap_tolerant_count"
                  fill={COLORS[0]}
                  radius={[0, 4, 4, 0]}
                  name="Gap Tolerant"
                />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 5. Response Rates */}
        <Card>
          <CardHeader>
            <CardTitle>Response Rates</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={responseRates}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="method" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Bar
                  dataKey="interviews"
                  stackId="responses"
                  fill={COLORS[0]}
                  name="Interviews"
                />
                <Bar
                  dataKey="offers"
                  stackId="responses"
                  fill={COLORS[2]}
                  name="Offers"
                />
                <Bar
                  dataKey="rejections"
                  stackId="responses"
                  fill={COLORS[3]}
                  name="Rejections"
                />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 6. Route Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Route Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={routeBreakdown}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  paddingAngle={2}
                  label={renderPercentLabel}
                >
                  {routeBreakdown.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

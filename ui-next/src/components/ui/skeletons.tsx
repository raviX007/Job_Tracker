import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ─── SkeletonCard ─────────────────────────────────────

interface SkeletonCardProps {
  lines?: number;
  header?: boolean;
  avatar?: boolean;
  className?: string;
}

export function SkeletonCard({
  lines = 3,
  header = true,
  avatar = false,
  className,
}: SkeletonCardProps) {
  return (
    <Card className={className}>
      {header && (
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-24" />
        </CardHeader>
      )}
      <CardContent className={cn("space-y-2", !header && "pt-6")}>
        {avatar && (
          <div className="flex items-center gap-3">
            <Skeleton className="h-9 w-9 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
        )}
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className={cn("h-4", i === lines - 1 ? "w-3/4" : "w-full")}
          />
        ))}
      </CardContent>
    </Card>
  );
}

// ─── SkeletonGrid ─────────────────────────────────────

interface SkeletonGridProps {
  count?: number;
  columns?: string;
  cardProps?: Omit<SkeletonCardProps, "className">;
}

export function SkeletonGrid({
  count = 6,
  columns = "grid-cols-1 md:grid-cols-2",
  cardProps,
}: SkeletonGridProps) {
  return (
    <div className={cn("grid gap-4", columns)}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} {...cardProps} />
      ))}
    </div>
  );
}

// ─── SkeletonTable ────────────────────────────────────

interface SkeletonTableProps {
  rows?: number;
  columns?: string[] | number;
}

export function SkeletonTable({
  rows = 8,
  columns = 6,
}: SkeletonTableProps) {
  const colArray =
    typeof columns === "number"
      ? Array.from({ length: columns }, (_, i) => `Col ${i + 1}`)
      : columns;

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-primary text-white text-xs uppercase">
              <tr>
                {colArray.map((col) => (
                  <th key={col} className="px-3 py-2.5 text-left">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {Array.from({ length: rows }).map((_, i) => (
                <tr key={i}>
                  {colArray.map((_, j) => (
                    <td key={j} className="px-3 py-2.5">
                      <Skeleton className="h-5 w-full" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── SkeletonChart ────────────────────────────────────

interface SkeletonChartProps {
  height?: string;
  showTitle?: boolean;
}

export function SkeletonChart({
  height = "h-[280px]",
  showTitle = true,
}: SkeletonChartProps) {
  return (
    <Card>
      {showTitle && (
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
      )}
      <CardContent>
        <Skeleton className={cn(height, "w-full rounded-lg")} />
      </CardContent>
    </Card>
  );
}

// ─── SkeletonKpiRow ───────────────────────────────────

interface SkeletonKpiRowProps {
  count?: number;
  columns?: string;
}

export function SkeletonKpiRow({
  count = 4,
  columns = "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
}: SkeletonKpiRowProps) {
  return (
    <div className={cn("grid gap-4", columns)}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-4 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-16" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

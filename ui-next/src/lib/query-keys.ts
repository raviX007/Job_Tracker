export const queryKeys = {
  overview: (pid: number) => ["overview", pid] as const,
  dailyTrends: (pid: number, days: number) => ["dailyTrends", pid, days] as const,
  applications: (pid: number, filters: Record<string, unknown>) =>
    ["applications", pid, filters] as const,
  sources: (pid: number) => ["sources", pid] as const,
  emails: (pid: number, status: string, source: string) =>
    ["emails", pid, status, source] as const,
  emailStatuses: (pid: number) => ["emailStatuses", pid] as const,
  emailSources: (pid: number) => ["emailSources", pid] as const,
  appsForUpdate: (pid: number) => ["appsForUpdate", pid] as const,
  analyzedJobs: (pid: number) => ["analyzedJobs", pid] as const,
  analytics: (pid: number) => ["analytics", pid] as const,
  tracker: (pid: number) => ["tracker", pid] as const,
  startups: (pid: number, filters: Record<string, unknown>) =>
    ["startups", pid, filters] as const,
  startupStats: (pid: number) => ["startupStats", pid] as const,
  startupSources: (pid: number) => ["startupSources", pid] as const,
};

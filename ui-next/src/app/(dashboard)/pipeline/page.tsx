"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { runMainPipeline, runStartupScout, getPipelineRunStatus } from "@/lib/api";
import { isDemoMode } from "@/hooks/use-profile";
import { useAuth } from "@/hooks/use-auth";
import { cn, stripAnsi } from "@/lib/utils";
import { PageHeader, SectionHeader } from "@/components/layout/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { PIPELINE_SOURCES, STARTUP_SOURCES } from "@/lib/constants";

type RunStatus = "idle" | "running" | "completed" | "failed";

const PIPELINE_STEPS = [
  { step: 1, description: "Scrape job listings from configured sources" },
  { step: 2, description: "Deduplicate against existing jobs in the database" },
  { step: 3, description: "Pre-filter jobs using keyword and location rules" },
  { step: 4, description: "Generate embeddings for semantic matching" },
  { step: 5, description: "LLM analysis for scoring, decision, and email drafting" },
  { step: 6, description: "Save analyzed jobs and emails to the database" },
];

const SOURCE_GROUPS = [
  { group: "Remote Boards", scrapers: "Remotive, Jobicy, Himalayas, Arbeitnow, RemoteOK", auth: "No" },
  { group: "Aggregators", scrapers: "Jooble, Adzuna, HiringCafe", auth: "API Key" },
  { group: "API Boards", scrapers: "JSearch, CareerJet, TheMuse, FindWork", auth: "API Key" },
  { group: "ATS Direct", scrapers: "Greenhouse, Lever", auth: "No" },
];

const STARTUP_STEPS = [
  { step: 1, description: "Scrape startup profiles from configured sources" },
  { step: 2, description: "Extract founder info, funding data, and tech stack" },
  { step: 3, description: "Match startups against your profile for relevance scoring" },
  { step: 4, description: "Generate cold outreach emails for top matches" },
];

const STARTUP_SOURCE_GROUPS = [
  { source: "HN Who's Hiring", description: "Monthly Hacker News hiring threads", auth: "No" },
  { source: "YC Directory", description: "Y Combinator startup directory", auth: "No" },
  { source: "ProductHunt", description: "Recently launched products", auth: "No" },
];

const POLL_INTERVAL_MS = 3000;

function StatusIndicator({ status, message, duration }: { status: RunStatus; message: string; duration?: number | null }) {
  if (status === "idle") return null;

  return (
    <div
      className={cn(
        "mt-4 rounded-lg border px-4 py-3 text-sm",
        status === "running" && "border-blue-200 bg-blue-50 text-blue-700",
        status === "completed" && "border-emerald-200 bg-emerald-50 text-emerald-700",
        status === "failed" && "border-red-200 bg-red-50 text-red-700",
      )}
    >
      <div className="flex items-center gap-2">
        {status === "running" && (
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        <span className="font-medium">
          {status === "running" && "Pipeline running..."}
          {status === "completed" && "Completed"}
          {status === "failed" && "Failed"}
        </span>
        {duration != null && (
          <span className="text-xs opacity-70">({duration.toFixed(1)}s)</span>
        )}
      </div>
      {message && <p className="mt-1">{message}</p>}
    </div>
  );
}

function OutputLog({ output }: { output: string }) {
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [output]);

  if (!output) return null;

  return (
    <pre
      ref={logRef}
      className="mt-4 max-h-80 overflow-auto rounded-lg border border-border bg-gray-900 p-4 font-mono text-xs leading-relaxed text-green-400"
    >
      {stripAnsi(output)}
    </pre>
  );
}

export default function PipelinePage() {
  const demoMode = isDemoMode();
  const { canEdit } = useAuth();

  // Main pipeline state
  const [pipelineSource, setPipelineSource] = useState<string>("all");
  const [pipelineLimit, setPipelineLimit] = useState<number>(10);
  const [pipelineStatus, setPipelineStatus] = useState<RunStatus>("idle");
  const [pipelineMessage, setPipelineMessage] = useState("");
  const [pipelineOutput, setPipelineOutput] = useState("");
  const [pipelineDuration, setPipelineDuration] = useState<number | null>(null);
  const pipelineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Startup scout state
  const [startupSource, setStartupSource] = useState<string>("startup_scout");
  const [startupLimit, setStartupLimit] = useState<number>(10);
  const [startupStatus, setStartupStatus] = useState<RunStatus>("idle");
  const [startupMessage, setStartupMessage] = useState("");
  const [startupOutput, setStartupOutput] = useState("");
  const [startupDuration, setStartupDuration] = useState<number | null>(null);
  const startupIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pipelineIntervalRef.current) clearInterval(pipelineIntervalRef.current);
      if (startupIntervalRef.current) clearInterval(startupIntervalRef.current);
    };
  }, []);

  const pollRun = useCallback(
    (
      runId: string,
      setStatus: (s: RunStatus) => void,
      setMessage: (m: string) => void,
      setOutput: (o: string) => void,
      setDuration: (d: number | null) => void,
      intervalRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>,
    ) => {
      intervalRef.current = setInterval(async () => {
        try {
          const run = await getPipelineRunStatus(runId);
          setOutput(run.output || "");

          if (run.status === "completed" || run.status === "failed") {
            if (intervalRef.current) clearInterval(intervalRef.current);
            intervalRef.current = null;
            setStatus(run.status === "completed" ? "completed" : "failed");
            setDuration(run.duration_seconds);
            if (run.error) {
              setMessage(run.error);
            } else if (run.status === "completed") {
              setMessage("Pipeline finished successfully");
            }
          }
        } catch {
          // Polling error — don't stop, just skip this tick
        }
      }, POLL_INTERVAL_MS);
    },
    [],
  );

  async function handleRunPipeline() {
    setPipelineStatus("running");
    setPipelineMessage("");
    setPipelineOutput("");
    setPipelineDuration(null);
    try {
      const result = await runMainPipeline(pipelineSource, pipelineLimit);
      pollRun(
        result.run_id,
        setPipelineStatus,
        setPipelineMessage,
        setPipelineOutput,
        setPipelineDuration,
        pipelineIntervalRef,
      );
    } catch (err) {
      setPipelineStatus("failed");
      setPipelineMessage(err instanceof Error ? err.message : "Failed to start pipeline");
    }
  }

  async function handleRunStartup() {
    setStartupStatus("running");
    setStartupMessage("");
    setStartupOutput("");
    setStartupDuration(null);
    try {
      const result = await runStartupScout(startupSource, startupLimit);
      pollRun(
        result.run_id,
        setStartupStatus,
        setStartupMessage,
        setStartupOutput,
        setStartupDuration,
        startupIntervalRef,
      );
    } catch (err) {
      setStartupStatus("failed");
      setStartupMessage(err instanceof Error ? err.message : "Failed to start startup scout");
    }
  }

  return (
    <div>
      <PageHeader
        title="Pipeline Runner"
        subtitle="Scrape → Dedup → Pre-filter → Embed → LLM Analyze → Save to DB"
      />

      {demoMode && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          Pipeline execution is disabled in demo mode.
        </div>
      )}

      {/* Main Pipeline Section */}
      <Card>
        <CardHeader>
          <CardTitle>Main Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-64">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">
                Source
              </label>
              <Select value={pipelineSource} onValueChange={setPipelineSource}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PIPELINE_SOURCES).map(([label, value]) => (
                    <SelectItem key={value ?? label} value={value ?? label}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-32">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">
                Limit
              </label>
              <Input
                type="number"
                min={1}
                max={100}
                value={pipelineLimit}
                onChange={(e) =>
                  setPipelineLimit(Math.min(100, Math.max(1, parseInt(e.target.value) || 1)))
                }
              />
            </div>

            <Button
              variant="accent"
              onClick={handleRunPipeline}
              disabled={demoMode || !canEdit || pipelineStatus === "running"}
            >
              {pipelineStatus === "running" ? "Running..." : "Run Pipeline"}
            </Button>
          </div>

          <StatusIndicator status={pipelineStatus} message={pipelineMessage} duration={pipelineDuration} />
          <OutputLog output={pipelineOutput} />
        </CardContent>
      </Card>

      <Separator className="my-8" />

      {/* Startup Scout Section */}
      <Card>
        <CardHeader>
          <CardTitle>Startup Scout</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-64">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">
                Source
              </label>
              <Select value={startupSource} onValueChange={setStartupSource}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(STARTUP_SOURCES).map(([label, value]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-32">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">
                Limit
              </label>
              <Input
                type="number"
                min={1}
                max={100}
                value={startupLimit}
                onChange={(e) =>
                  setStartupLimit(Math.min(100, Math.max(1, parseInt(e.target.value) || 1)))
                }
              />
            </div>

            <Button
              variant="accent"
              onClick={handleRunStartup}
              disabled={demoMode || !canEdit || startupStatus === "running"}
            >
              {startupStatus === "running" ? "Running..." : "Run Startup Scout"}
            </Button>
          </div>

          <StatusIndicator status={startupStatus} message={startupMessage} duration={startupDuration} />
          <OutputLog output={startupOutput} />
        </CardContent>
      </Card>

      {/* Pipeline Info Section */}
      <SectionHeader title="Pipeline Information" />

      {/* Pipeline Steps Table */}
      <div className="mb-8">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Pipeline Steps</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Step</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Description</th>
              </tr>
            </thead>
            <tbody>
              {PIPELINE_STEPS.map((row) => (
                <tr key={row.step} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2.5 font-mono text-gray-500">{row.step}</td>
                  <td className="px-4 py-2.5 text-gray-800">{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Source Groups Table */}
      <div className="mb-8">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Source Groups</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Group</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Scrapers</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Auth Required</th>
              </tr>
            </thead>
            <tbody>
              {SOURCE_GROUPS.map((row) => (
                <tr key={row.group} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2.5 font-medium text-gray-800">{row.group}</td>
                  <td className="px-4 py-2.5 text-gray-600">{row.scrapers}</td>
                  <td className="px-4 py-2.5 text-gray-600">{row.auth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Startup Scout Steps */}
      <div className="mb-8">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Startup Scout Steps</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Step</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Description</th>
              </tr>
            </thead>
            <tbody>
              {STARTUP_STEPS.map((row) => (
                <tr key={row.step} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2.5 font-mono text-gray-500">{row.step}</td>
                  <td className="px-4 py-2.5 text-gray-800">{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Startup Sources Table */}
      <div className="mb-8">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Startup Sources</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Source</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Description</th>
                <th className="px-4 py-2.5 text-left font-medium text-gray-600">Auth Required</th>
              </tr>
            </thead>
            <tbody>
              {STARTUP_SOURCE_GROUPS.map((row) => (
                <tr key={row.source} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2.5 font-medium text-gray-800">{row.source}</td>
                  <td className="px-4 py-2.5 text-gray-600">{row.description}</td>
                  <td className="px-4 py-2.5 text-gray-600">{row.auth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

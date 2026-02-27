"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useProfile } from "@/hooks/use-profile";
import { useAuth } from "@/hooks/use-auth";
import { useResumeUpload } from "@/hooks/use-resume-upload";
import { getMyProfile, saveMyProfile } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Save, Loader2, Check } from "lucide-react";
import { TagInput } from "./components/tag-input";
import { ResumeUpload } from "./components/resume-upload";

// ─── Default profile config ────────────────────────────

function defaultConfig() {
  return {
    candidate: { name: "", email: "", phone: "", resume_path: "", github: "", linkedin: "", portfolio: "", location: "", timezone: "Asia/Kolkata" },
    skills: { primary: [] as string[], secondary: [] as string[], frameworks: [] as string[] },
    experience: { years: 0, graduation_year: 2023, degree: "", gap_explanation: "", work_history: [] as any[], gap_projects: [] as any[] },
    search_preferences: {
      mode: "hybrid", locations: [] as string[],
      remote_preferences: { accept_global_remote: false, accept_country_remote: true, country: "India", timezone_range: "IST ± 2hrs", visa_sponsorship_needed: false },
      relocation_willing: false, salary_min: 0, salary_currency: "INR",
    },
    filters: { must_have_any: [] as string[], skip_titles: [] as string[], skip_companies: [] as string[], target_companies: [] as string[], min_match_score: 40, auto_apply_threshold: 60, maybe_range: [40, 60] },
    matching: { embedding_model: "all-MiniLM-L6-v2", fast_filter_threshold: 0.45, max_job_age_days: 7, prefer_gap_tolerant: true, prefer_fresher_roles: true },
    screening_answers: { work_authorization_india: "Yes", visa_sponsorship_required: "No", willing_to_relocate: "Yes", notice_period: "Immediate", expected_ctc_range: "4-8 LPA", years_of_experience: "0-1", current_location: "Bengaluru", unknown_question_action: "skip_and_alert" },
    llm: { provider: "openai", model: "gpt-4o-mini", temperature: 0.3, max_tokens: 1500, json_mode: true },
    cold_email: { sender_email: "", sender_name: "", max_daily: 12, max_per_hour: 8, morning_batch_time: "09:00", signature: "", delay_between_sends_sec: 5, delay_jitter_sec: 3, warmup_enabled: true, include_unsubscribe: true, max_followups_per_recipient: 1, followup_after_days: 7, only_business_emails: true },
    safety: { max_applications_per_company_per_month: 2, require_review_above_score: 85, auto_submit_platforms: ["naukri", "indeed", "foundit"], followup_after_days: 7, followup_max_per_email: 1 },
    dream_companies: [] as string[],
    anti_hallucination: { strict_mode: true, validate_output: true, allowed_companies: [] as string[] },
    notifications: { telegram: { enabled: false, bot_token: "", channels: { urgent: "", digest: "", review: "" }, review_batch_interval_hours: 2, digest_time: "20:00" } },
    system: { active: true, platforms: { naukri: true, indeed: true, foundit: true, cold_email: true, scraping: true } },
    platforms: {} as Record<string, any>,
    aggregators: {} as Record<string, any>,
  };
}

type Config = ReturnType<typeof defaultConfig>;

// ─── Field helpers ──────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-medium text-muted-foreground">{children}</label>;
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
      {label}
    </label>
  );
}

// ─── Main page ──────────────────────────────────────────

export default function SettingsPage() {
  const { setProfileId } = useProfile();
  const { canEdit } = useAuth();
  const { isUploading: isResumeUploading } = useResumeUpload();
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<Config>(defaultConfig());
  const [resumeFilename, setResumeFilename] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["myProfile"],
    queryFn: ({ signal }) => getMyProfile(signal),
  });

  // Populate form when data loads
  useEffect(() => {
    if (data?.profile?.config) {
      const d = defaultConfig();
      const c = data.profile.config;
      const merged = { ...d, ...c };
      // Deep merge nested objects
      merged.candidate = { ...d.candidate, ...c.candidate };
      merged.skills = { ...d.skills, ...c.skills };
      merged.experience = { ...d.experience, ...c.experience };
      merged.search_preferences = { ...d.search_preferences, ...c.search_preferences };
      merged.filters = { ...d.filters, ...c.filters };
      merged.matching = { ...d.matching, ...c.matching };
      merged.screening_answers = { ...d.screening_answers, ...c.screening_answers };
      merged.llm = { ...d.llm, ...c.llm };
      merged.cold_email = { ...d.cold_email, ...c.cold_email };
      merged.safety = { ...d.safety, ...c.safety };
      // Ensure arrays are never null (server data can have null arrays after auto-save merge)
      merged.skills.primary = merged.skills.primary || [];
      merged.skills.secondary = merged.skills.secondary || [];
      merged.skills.frameworks = merged.skills.frameworks || [];
      merged.experience.work_history = merged.experience.work_history || [];
      merged.experience.gap_projects = merged.experience.gap_projects || [];
      merged.filters.must_have_any = merged.filters.must_have_any || [];
      merged.filters.skip_titles = merged.filters.skip_titles || [];
      merged.filters.skip_companies = merged.filters.skip_companies || [];
      merged.filters.target_companies = merged.filters.target_companies || [];
      merged.search_preferences.locations = merged.search_preferences.locations || [];
      merged.dream_companies = merged.dream_companies || [];
      setConfig(merged);
      setResumeFilename(data.profile.resume_filename || null);
      if (data.profile.id) setProfileId(data.profile.id);
    }
  }, [data, setProfileId]);

  const saveMutation = useMutation({
    mutationFn: () => saveMyProfile(config),
    onSuccess: (result: any) => {
      if (result.profile_id) setProfileId(result.profile_id);
      queryClient.invalidateQueries({ queryKey: ["myProfile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  // Update helpers
  function updateCandidate(field: string, value: string) {
    setConfig((prev) => ({ ...prev, candidate: { ...prev.candidate, [field]: value } }));
  }
  function updateSkills(field: string, value: string[]) {
    setConfig((prev) => ({ ...prev, skills: { ...prev.skills, [field]: value } }));
  }
  function updateExperience(field: string, value: any) {
    setConfig((prev) => ({ ...prev, experience: { ...prev.experience, [field]: value } }));
  }
  function updateSearch(field: string, value: any) {
    setConfig((prev) => ({ ...prev, search_preferences: { ...prev.search_preferences, [field]: value } }));
  }
  function updateFilters(field: string, value: any) {
    setConfig((prev) => ({ ...prev, filters: { ...prev.filters, [field]: value } }));
  }
  function updateMatching(field: string, value: any) {
    setConfig((prev) => ({ ...prev, matching: { ...prev.matching, [field]: value } }));
  }
  function updateColdEmail(field: string, value: any) {
    setConfig((prev) => ({ ...prev, cold_email: { ...prev.cold_email, [field]: value } }));
  }
  function updateScreening(field: string, value: string) {
    setConfig((prev) => ({ ...prev, screening_answers: { ...prev.screening_answers, [field]: value } }));
  }
  function updateLLM(field: string, value: any) {
    setConfig((prev) => ({ ...prev, llm: { ...prev.llm, [field]: value } }));
  }

  // Resume extraction callback — merge locally + refresh from DB (auto-saved)
  const handleResumeExtracted = useCallback((extracted: any) => {
    if (!extracted) return;
    setConfig((prev) => ({
      ...prev,
      candidate: { ...prev.candidate, ...(extracted.candidate || {}) },
      skills: {
        ...prev.skills,
        ...(extracted.skills || {}),
        // Ensure arrays survive the merge (never null)
        primary: extracted.skills?.primary || prev.skills.primary || [],
        secondary: extracted.skills?.secondary || prev.skills.secondary || [],
        frameworks: extracted.skills?.frameworks || prev.skills.frameworks || [],
      },
      experience: {
        ...prev.experience,
        ...(extracted.experience || {}),
        // Ensure arrays survive the merge (never null)
        work_history: extracted.experience?.work_history || prev.experience.work_history || [],
        gap_projects: extracted.experience?.gap_projects || prev.experience.gap_projects || [],
      },
    }));
    queryClient.invalidateQueries({ queryKey: ["myProfile"] });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [queryClient]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isNewProfile = !data?.profile?.config;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">
            {isNewProfile ? "Set up your profile to get started" : "Manage your profile and pipeline configuration"}
          </p>
        </div>
        <Button
          variant="accent"
          onClick={() => saveMutation.mutate()}
          disabled={!canEdit || saveMutation.isPending || isResumeUploading || !config.candidate.name}
        >
          {saveMutation.isPending ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</>
          ) : saved ? (
            <><Check className="mr-2 h-4 w-4" />Saved</>
          ) : (
            <><Save className="mr-2 h-4 w-4" />Save Profile</>
          )}
        </Button>
      </div>

      {saveMutation.isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          Failed to save: {(saveMutation.error as Error).message}
        </div>
      )}

      <fieldset disabled={!canEdit} className="space-y-6">
      <Tabs defaultValue="profile" className="space-y-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          {["skills", "experience", "search", "filters", "email", "advanced"].map((tab) => (
            <TabsTrigger key={tab} value={tab} disabled={isResumeUploading} title={isResumeUploading ? "Please wait until resume extraction is complete" : undefined}>
              {tab === "email" ? "Email & Safety" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* ─── Profile Tab ─────────────────────────── */}
        <TabsContent value="profile" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Resume Upload</CardTitle></CardHeader>
            <CardContent>
              <ResumeUpload
                onExtracted={handleResumeExtracted}
                currentFilename={resumeFilename}
                disabled={!canEdit}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Candidate Information</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Full Name *</FieldLabel><Input value={config.candidate.name} onChange={(e) => updateCandidate("name", e.target.value)} /></div>
                <div><FieldLabel>Email *</FieldLabel><Input type="email" value={config.candidate.email} onChange={(e) => updateCandidate("email", e.target.value)} /></div>
                <div><FieldLabel>Phone</FieldLabel><Input value={config.candidate.phone} onChange={(e) => updateCandidate("phone", e.target.value)} /></div>
              </FieldRow>
              <FieldRow>
                <div><FieldLabel>Location *</FieldLabel><Input value={config.candidate.location} onChange={(e) => updateCandidate("location", e.target.value)} /></div>
                <div><FieldLabel>Timezone</FieldLabel><Input value={config.candidate.timezone} onChange={(e) => updateCandidate("timezone", e.target.value)} /></div>
              </FieldRow>
              <FieldRow>
                <div><FieldLabel>GitHub</FieldLabel><Input value={config.candidate.github} onChange={(e) => updateCandidate("github", e.target.value)} /></div>
                <div><FieldLabel>LinkedIn</FieldLabel><Input value={config.candidate.linkedin} onChange={(e) => updateCandidate("linkedin", e.target.value)} /></div>
                <div><FieldLabel>Portfolio</FieldLabel><Input value={config.candidate.portfolio} onChange={(e) => updateCandidate("portfolio", e.target.value)} /></div>
              </FieldRow>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Skills Tab ──────────────────────────── */}
        <TabsContent value="skills" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Skills</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div><FieldLabel>Primary Skills (languages & core frameworks)</FieldLabel><TagInput value={config.skills.primary} onChange={(v) => updateSkills("primary", v)} placeholder="e.g. Python, React, Django" /></div>
              <div><FieldLabel>Secondary Skills (databases, tools, DevOps)</FieldLabel><TagInput value={config.skills.secondary} onChange={(v) => updateSkills("secondary", v)} placeholder="e.g. PostgreSQL, Docker, Redis" /></div>
              <div><FieldLabel>Frameworks & Libraries</FieldLabel><TagInput value={config.skills.frameworks} onChange={(v) => updateSkills("frameworks", v)} placeholder="e.g. RAG, LangChain, OpenAI" /></div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Experience Tab ──────────────────────── */}
        <TabsContent value="experience" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Education & Background</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Years of Experience</FieldLabel><Input type="number" min={0} value={config.experience.years} onChange={(e) => updateExperience("years", parseInt(e.target.value) || 0)} /></div>
                <div><FieldLabel>Graduation Year</FieldLabel><Input type="number" value={config.experience.graduation_year} onChange={(e) => updateExperience("graduation_year", parseInt(e.target.value) || 2023)} /></div>
                <div><FieldLabel>Degree</FieldLabel><Input value={config.experience.degree} onChange={(e) => updateExperience("degree", e.target.value)} /></div>
              </FieldRow>
              <div><FieldLabel>Gap Explanation (if applicable)</FieldLabel><Textarea value={config.experience.gap_explanation} onChange={(e) => updateExperience("gap_explanation", e.target.value)} rows={2} /></div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Work History</CardTitle>
              <Button variant="outline" size="sm" onClick={() => updateExperience("work_history", [...(config.experience.work_history || []), { company: "", role: "", duration: "", type: "full_time", tech: [], description: "", projects: [] }])}>
                Add Entry
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {(config.experience.work_history || []).length === 0 && <p className="text-sm text-muted-foreground">No work history added. Upload a resume to auto-fill.</p>}
              {(config.experience.work_history || []).map((entry: any, i: number) => (
                <div key={i} className="space-y-3 rounded-lg border p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Entry {i + 1}</span>
                    <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700" onClick={() => updateExperience("work_history", config.experience.work_history.filter((_: any, j: number) => j !== i))}>Remove</Button>
                  </div>
                  <FieldRow>
                    <div><FieldLabel>Company</FieldLabel><Input value={entry.company} onChange={(e) => { const wh = [...config.experience.work_history]; wh[i] = { ...wh[i], company: e.target.value }; updateExperience("work_history", wh); }} /></div>
                    <div><FieldLabel>Role</FieldLabel><Input value={entry.role} onChange={(e) => { const wh = [...config.experience.work_history]; wh[i] = { ...wh[i], role: e.target.value }; updateExperience("work_history", wh); }} /></div>
                    <div><FieldLabel>Duration</FieldLabel><Input value={entry.duration} onChange={(e) => { const wh = [...config.experience.work_history]; wh[i] = { ...wh[i], duration: e.target.value }; updateExperience("work_history", wh); }} placeholder="e.g. Jun 2024 – Sep 2024" /></div>
                  </FieldRow>
                  <div><FieldLabel>Description</FieldLabel><Textarea value={entry.description} onChange={(e) => { const wh = [...config.experience.work_history]; wh[i] = { ...wh[i], description: e.target.value }; updateExperience("work_history", wh); }} rows={2} /></div>
                  <div><FieldLabel>Technologies</FieldLabel><TagInput value={entry.tech || []} onChange={(v) => { const wh = [...config.experience.work_history]; wh[i] = { ...wh[i], tech: v }; updateExperience("work_history", wh); }} /></div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Projects</CardTitle>
              <Button variant="outline" size="sm" onClick={() => updateExperience("gap_projects", [...(config.experience.gap_projects || []), { name: "", description: "", tech: [] }])}>
                Add Project
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {(config.experience.gap_projects || []).length === 0 && <p className="text-sm text-muted-foreground">No projects added yet.</p>}
              {(config.experience.gap_projects || []).map((proj: any, i: number) => (
                <div key={i} className="space-y-3 rounded-lg border p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Project {i + 1}</span>
                    <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700" onClick={() => updateExperience("gap_projects", config.experience.gap_projects.filter((_: any, j: number) => j !== i))}>Remove</Button>
                  </div>
                  <FieldRow>
                    <div><FieldLabel>Name</FieldLabel><Input value={proj.name} onChange={(e) => { const gp = [...config.experience.gap_projects]; gp[i] = { ...gp[i], name: e.target.value }; updateExperience("gap_projects", gp); }} /></div>
                  </FieldRow>
                  <div><FieldLabel>Description</FieldLabel><Textarea value={proj.description} onChange={(e) => { const gp = [...config.experience.gap_projects]; gp[i] = { ...gp[i], description: e.target.value }; updateExperience("gap_projects", gp); }} rows={2} /></div>
                  <div><FieldLabel>Technologies</FieldLabel><TagInput value={proj.tech || []} onChange={(v) => { const gp = [...config.experience.gap_projects]; gp[i] = { ...gp[i], tech: v }; updateExperience("gap_projects", gp); }} /></div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Search Tab ──────────────────────────── */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Search Preferences</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div>
                  <FieldLabel>Mode</FieldLabel>
                  <select value={config.search_preferences.mode} onChange={(e) => updateSearch("mode", e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="hybrid">Hybrid</option>
                    <option value="remote">Remote</option>
                    <option value="onsite">Onsite</option>
                  </select>
                </div>
                <div><FieldLabel>Salary Min</FieldLabel><Input type="number" value={config.search_preferences.salary_min} onChange={(e) => updateSearch("salary_min", parseInt(e.target.value) || 0)} /></div>
                <div><FieldLabel>Currency</FieldLabel><Input value={config.search_preferences.salary_currency} onChange={(e) => updateSearch("salary_currency", e.target.value)} /></div>
              </FieldRow>
              <div><FieldLabel>Preferred Locations</FieldLabel><TagInput value={config.search_preferences.locations} onChange={(v) => updateSearch("locations", v)} placeholder="e.g. Bangalore, Remote India" /></div>
              <div className="space-y-2">
                <Toggle label="Accept global remote" checked={config.search_preferences.remote_preferences?.accept_global_remote ?? false} onChange={(v) => updateSearch("remote_preferences", { ...config.search_preferences.remote_preferences, accept_global_remote: v })} />
                <Toggle label="Accept country remote" checked={config.search_preferences.remote_preferences?.accept_country_remote ?? true} onChange={(v) => updateSearch("remote_preferences", { ...config.search_preferences.remote_preferences, accept_country_remote: v })} />
                <Toggle label="Willing to relocate" checked={config.search_preferences.relocation_willing} onChange={(v) => updateSearch("relocation_willing", v)} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Filters Tab ─────────────────────────── */}
        <TabsContent value="filters" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Job Filters</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div><FieldLabel>Must Have Any (keywords)</FieldLabel><TagInput value={config.filters.must_have_any} onChange={(v) => updateFilters("must_have_any", v)} placeholder="e.g. python, react, AI" /></div>
              <div><FieldLabel>Skip Titles (exclude jobs with these words)</FieldLabel><TagInput value={config.filters.skip_titles} onChange={(v) => updateFilters("skip_titles", v)} placeholder="e.g. senior, lead, manager" /></div>
              <div><FieldLabel>Skip Companies</FieldLabel><TagInput value={config.filters.skip_companies} onChange={(v) => updateFilters("skip_companies", v)} /></div>
              <div><FieldLabel>Target Companies (priority)</FieldLabel><TagInput value={config.filters.target_companies} onChange={(v) => updateFilters("target_companies", v)} /></div>
              <FieldRow>
                <div><FieldLabel>Min Match Score (0-100)</FieldLabel><Input type="number" min={0} max={100} value={config.filters.min_match_score} onChange={(e) => updateFilters("min_match_score", parseInt(e.target.value) || 0)} /></div>
                <div><FieldLabel>Auto Apply Threshold (0-100)</FieldLabel><Input type="number" min={0} max={100} value={config.filters.auto_apply_threshold} onChange={(e) => updateFilters("auto_apply_threshold", parseInt(e.target.value) || 0)} /></div>
              </FieldRow>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Matching</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Embedding Model</FieldLabel><Input value={config.matching.embedding_model} onChange={(e) => updateMatching("embedding_model", e.target.value)} /></div>
                <div><FieldLabel>Similarity Threshold (0-1)</FieldLabel><Input type="number" step={0.05} min={0} max={1} value={config.matching.fast_filter_threshold} onChange={(e) => updateMatching("fast_filter_threshold", parseFloat(e.target.value) || 0.45)} /></div>
                <div><FieldLabel>Max Job Age (days)</FieldLabel><Input type="number" min={1} max={30} value={config.matching.max_job_age_days} onChange={(e) => updateMatching("max_job_age_days", parseInt(e.target.value) || 7)} /></div>
              </FieldRow>
              <div className="space-y-2">
                <Toggle label="Prefer gap-tolerant roles" checked={config.matching.prefer_gap_tolerant} onChange={(v) => updateMatching("prefer_gap_tolerant", v)} />
                <Toggle label="Prefer fresher roles" checked={config.matching.prefer_fresher_roles} onChange={(v) => updateMatching("prefer_fresher_roles", v)} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Email & Safety Tab ──────────────────── */}
        <TabsContent value="email" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Cold Email</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Sender Name</FieldLabel><Input value={config.cold_email.sender_name} onChange={(e) => updateColdEmail("sender_name", e.target.value)} /></div>
                <div><FieldLabel>Sender Email</FieldLabel><Input type="email" value={config.cold_email.sender_email} onChange={(e) => updateColdEmail("sender_email", e.target.value)} /></div>
              </FieldRow>
              <FieldRow>
                <div><FieldLabel>Max Daily</FieldLabel><Input type="number" min={0} max={50} value={config.cold_email.max_daily} onChange={(e) => updateColdEmail("max_daily", parseInt(e.target.value) || 0)} /></div>
                <div><FieldLabel>Max Per Hour</FieldLabel><Input type="number" min={0} max={20} value={config.cold_email.max_per_hour} onChange={(e) => updateColdEmail("max_per_hour", parseInt(e.target.value) || 0)} /></div>
                <div><FieldLabel>Follow-up After Days</FieldLabel><Input type="number" min={3} max={14} value={config.cold_email.followup_after_days} onChange={(e) => updateColdEmail("followup_after_days", parseInt(e.target.value) || 7)} /></div>
              </FieldRow>
              <div><FieldLabel>Email Signature</FieldLabel><Textarea value={config.cold_email.signature} onChange={(e) => updateColdEmail("signature", e.target.value)} rows={3} /></div>
              <div className="space-y-2">
                <Toggle label="Warmup enabled" checked={config.cold_email.warmup_enabled} onChange={(v) => updateColdEmail("warmup_enabled", v)} />
                <Toggle label="Include unsubscribe link" checked={config.cold_email.include_unsubscribe} onChange={(v) => updateColdEmail("include_unsubscribe", v)} />
                <Toggle label="Only business emails" checked={config.cold_email.only_business_emails} onChange={(v) => updateColdEmail("only_business_emails", v)} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Screening Answers</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Work Authorization (India)</FieldLabel><Input value={config.screening_answers.work_authorization_india} onChange={(e) => updateScreening("work_authorization_india", e.target.value)} /></div>
                <div><FieldLabel>Visa Sponsorship Required</FieldLabel><Input value={config.screening_answers.visa_sponsorship_required} onChange={(e) => updateScreening("visa_sponsorship_required", e.target.value)} /></div>
                <div><FieldLabel>Notice Period</FieldLabel><Input value={config.screening_answers.notice_period} onChange={(e) => updateScreening("notice_period", e.target.value)} /></div>
              </FieldRow>
              <FieldRow>
                <div><FieldLabel>Expected CTC Range</FieldLabel><Input value={config.screening_answers.expected_ctc_range} onChange={(e) => updateScreening("expected_ctc_range", e.target.value)} /></div>
                <div><FieldLabel>Years of Experience</FieldLabel><Input value={config.screening_answers.years_of_experience} onChange={(e) => updateScreening("years_of_experience", e.target.value)} /></div>
                <div><FieldLabel>Current Location</FieldLabel><Input value={config.screening_answers.current_location} onChange={(e) => updateScreening("current_location", e.target.value)} /></div>
              </FieldRow>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Safety</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Max Apps Per Company/Month</FieldLabel><Input type="number" min={1} max={5} value={config.safety.max_applications_per_company_per_month} onChange={(e) => setConfig((p) => ({ ...p, safety: { ...p.safety, max_applications_per_company_per_month: parseInt(e.target.value) || 2 } }))} /></div>
                <div><FieldLabel>Review Above Score</FieldLabel><Input type="number" min={50} max={100} value={config.safety.require_review_above_score} onChange={(e) => setConfig((p) => ({ ...p, safety: { ...p.safety, require_review_above_score: parseInt(e.target.value) || 85 } }))} /></div>
              </FieldRow>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Advanced Tab ────────────────────────── */}
        <TabsContent value="advanced" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">LLM Configuration</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <FieldRow>
                <div><FieldLabel>Provider</FieldLabel><Input value={config.llm.provider} onChange={(e) => updateLLM("provider", e.target.value)} /></div>
                <div><FieldLabel>Model</FieldLabel><Input value={config.llm.model} onChange={(e) => updateLLM("model", e.target.value)} /></div>
                <div><FieldLabel>Temperature (0-1)</FieldLabel><Input type="number" step={0.1} min={0} max={1} value={config.llm.temperature} onChange={(e) => updateLLM("temperature", parseFloat(e.target.value) || 0.3)} /></div>
              </FieldRow>
              <FieldRow>
                <div><FieldLabel>Max Tokens</FieldLabel><Input type="number" min={100} max={4000} value={config.llm.max_tokens} onChange={(e) => updateLLM("max_tokens", parseInt(e.target.value) || 1500)} /></div>
              </FieldRow>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Dream Companies</CardTitle></CardHeader>
            <CardContent>
              <TagInput value={config.dream_companies} onChange={(v) => setConfig((p) => ({ ...p, dream_companies: v }))} placeholder="e.g. Google, Microsoft, Razorpay" />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </fieldset>
    </div>
  );
}

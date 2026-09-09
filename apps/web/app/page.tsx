"use client";

import { CSSProperties, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeftRight,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  ExternalLink,
  FileSearch,
  Filter,
  FlaskConical,
  Loader2,
  MessageSquareText,
  Moon,
  Search,
  Sun,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Answer, Brief, EvidenceExtraction, EvidenceSource, EvalReport, RetrievedChunk, SourceType, Workspace, Usage, api } from "@/lib/api";
import { cn } from "@/lib/utils";

const sourceLabels: Record<SourceType, string> = {
  pubmed: "PubMed",
  clinical_trials: "ClinicalTrials.gov",
  fda_label: "FDA labels",
  fda_adverse_event: "FDA adverse reports",
};

type WorkspaceTab = "table" | "ask" | "sources" | "brief" | "reliability";

const navItems: { label: string; href: string; tab: WorkspaceTab }[] = [
  { label: "Workspace", href: "#workspace", tab: "table" },
  { label: "Ask", href: "#ask", tab: "ask" },
  { label: "Sources", href: "#sources", tab: "sources" },
];

const sourceFilterOptions: { label: string; value: SourceType | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Literature", value: "pubmed" },
  { label: "Trials", value: "clinical_trials" },
  { label: "FDA labels", value: "fda_label" },
  { label: "Adverse reports", value: "fda_adverse_event" },
];

const suggestedQuestions = [
  "What are the main benefits?",
  "What statistics support effectiveness?",
  "What are the main safety concerns?",
  "What trials are available?",
  "What does FDA labeling say?",
];

const RECENT_WORKSPACES_KEY = "triallens.recentWorkspaces";

type WorkflowStatus = "idle" | "retrieving sources" | "extracting fields" | "ready for synthesis" | "needs review" | "limited evidence";

export default function Home() {
  const [condition, setCondition] = useState("type 2 diabetes");
  const [intervention, setIntervention] = useState("metformin");
  const [question, setQuestion] = useState("What does the evidence say about benefits and safety limitations?");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [sources, setSources] = useState<EvidenceSource[]>([]);
  const [extractions, setExtractions] = useState<EvidenceExtraction[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [conversation, setConversation] = useState<Answer[]>([]);
  const [askFilter, setAskFilter] = useState<SourceType | "all">("all");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [evals, setEvals] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentWorkspaces, setRecentWorkspaces] = useState<Workspace[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>("idle");
  const [sourceFilter, setSourceFilter] = useState<SourceType | "all">("all");
  const [reviewFilter, setReviewFilter] = useState<"all" | "reviewed" | "unreviewed" | "needs_review">("all");
  const [quantOnly, setQuantOnly] = useState(false);
  const [selectedRow, setSelectedRow] = useState<EvidenceExtraction | null>(null);
  const [showAllRows, setShowAllRows] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("table");

  const counts = useMemo(() => {
    return sources.reduce<Record<string, number>>((acc, source) => {
      acc[source.source_type] = (acc[source.source_type] ?? 0) + 1;
      return acc;
    }, {});
  }, [sources]);

  const filteredExtractions = useMemo(() => {
    return extractions.filter((row) => {
      if (sourceFilter !== "all" && row.source_type !== sourceFilter) return false;
      if (reviewFilter !== "all" && row.review_status !== reviewFilter) return false;
      if (quantOnly && !row.has_quantitative_result) return false;
      return true;
    });
  }, [extractions, quantOnly, reviewFilter, sourceFilter]);

  const sourceTypesForAsk = askFilter === "all" ? null : [askFilter];
  const totalSources = sources.length;
  const isReady = Boolean(workspace && extractions.length > 0);
  const needsReviewCount = extractions.filter((row) => row.review_status === "needs_review").length;
  const visibleExtractions = showAllRows ? filteredExtractions : filteredExtractions.slice(0, 5);
  const hiddenExtractionCount = Math.max(filteredExtractions.length - visibleExtractions.length, 0);
  const visibleSources = showAllSources ? sources : sources.slice(0, 6);
  const hiddenSourceCount = Math.max(sources.length - visibleSources.length, 0);

  useEffect(() => {
    api.usage().then(setUsage).catch(() => setUsage(null));
    const cached = readCachedWorkspaces();
    if (cached.length) {
      setRecentWorkspaces(cached);
    }
    api
      .workspaces()
      .then((items) => {
        const merged = mergeRecentWorkspaces(items.slice(-4).reverse(), cached);
        setRecentWorkspaces(merged);
        writeCachedWorkspaces(merged);
      })
      .catch(() => {
        if (!cached.length) setRecentWorkspaces([]);
      });
  }, []);

  useEffect(() => {
    function syncTabFromHash() {
      const match = navItems.find((item) => item.href === window.location.hash);
      if (match) setActiveTab(match.tab);
    }

    syncTabFromHash();
    window.addEventListener("hashchange", syncTabFromHash);
    return () => window.removeEventListener("hashchange", syncTabFromHash);
  }, []);

  async function buildWorkspace(event?: FormEvent) {
    event?.preventDefault();
    if (busy || condition.trim().length < 2) return;
    setError(null);
    setAnswer(null);
    setConversation([]);
    setBrief(null);
    setEvals(null);
    setSources([]);
    setExtractions([]);
    setSelectedRow(null);
    setShowAllRows(false);
    setShowAllSources(false);
    setBusy("Creating workspace");
    setWorkflowStatus("retrieving sources");
    try {
      const created = await api.createWorkspace(condition.trim(), intervention.trim());
      setWorkspace(created);
      setBusy("Retrieving sources");
      const ingestResult = await api.ingest(created.id);
      setWorkflowStatus("extracting fields");
      const [indexed, extracted, generatedBrief, report] = await Promise.all([
        api.sources(created.id),
        api.extractions(created.id),
        api.brief(created.id),
        api.evals(),
      ]);
      setSources(indexed);
      setExtractions(extracted);
      setBrief(generatedBrief);
      setEvals(report);
      setWorkflowStatus(workflowStateFromCounts(indexed.length, ingestResult.extractions, extracted));
      setRecentWorkspaces((items) => {
        const next = mergeRecentWorkspaces([created], items);
        writeCachedWorkspaces(next);
        return next;
      });
      scrollToWorkspace();
    } catch (err) {
      setWorkflowStatus("limited evidence");
      setError(workspaceErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function reopenWorkspace(target: Workspace) {
    if (busy) return;
    setError(null);
    setBusy("Opening workspace");
    try {
      let [indexed, extracted, generatedBrief, report] = await Promise.all([
        api.sources(target.id),
        api.extractions(target.id),
        api.brief(target.id),
        api.evals(),
      ]);
      if (indexed.length === 0) {
        setBusy("Retrieving sources");
        await api.ingest(target.id);
        [indexed, extracted, generatedBrief, report] = await Promise.all([
          api.sources(target.id),
          api.extractions(target.id),
          api.brief(target.id),
          api.evals(),
        ]);
      }
      if (indexed.length > 0 && (extracted.length === 0 || extractionRowsNeedRefresh(extracted))) {
        setBusy("Extracting fields");
        await api.extract(target.id);
        extracted = await api.extractions(target.id);
      }
      setWorkspace(target);
      setCondition(target.condition);
      setIntervention(target.intervention ?? "");
      setSources(indexed);
      setExtractions(extracted);
      setBrief(generatedBrief);
      setEvals(report);
      setAnswer(null);
      setConversation(await api.answers(target.id));
      setSelectedRow(null);
      setShowAllRows(false);
      setShowAllSources(false);
      setWorkflowStatus(workflowStateFromCounts(indexed.length, extracted.length, extracted));
      setRecentWorkspaces((items) => {
        const next = mergeRecentWorkspaces([target], items);
        writeCachedWorkspaces(next);
        return next;
      });
      scrollToWorkspace();
    } catch (err) {
      setError(workspaceErrorMessage(err, "Could not reopen workspace."));
    } finally {
      setBusy(null);
    }
  }

  async function ask() {
    if (!workspace || busy || question.trim().length < 3) return;
    setError(null);
    setBusy("Synthesizing from evidence table");
    try {
      const response = await api.ask(workspace.id, question.trim(), sourceTypesForAsk, "workspace", null, answer?.id);
      setAnswer(response);
      api.usage().then(setUsage).catch(() => setUsage(null));
      setConversation((items) => [...items, response]);
      setQuestion("");
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          const answerResult = document.querySelector<HTMLElement>("#answer-result");
          answerResult?.focus({ preventScroll: true });
          answerResult?.scrollIntoView({ behavior: preferredScrollBehavior(), block: "start" });
        });
      });
    } catch (err) {
      setError(workspaceErrorMessage(err, "Question failed."));
    } finally {
      setBusy(null);
    }
  }

  async function saveToBrief(item: Answer, saved: boolean) {
    if (!workspace || busy) return;
    setBusy(saved ? "Saving to brief" : "Removing from brief");
    setError(null);
    try {
      const updated = await api.saveToBrief(workspace.id, item.id, saved);
      setConversation((items) => items.map((entry) => entry.id === updated.id ? updated : entry));
      if (answer?.id === updated.id) setAnswer(updated);
      setBrief(await api.brief(workspace.id));
    } catch (err) {
      setError(workspaceErrorMessage(err, "Could not update the brief. Try again."));
    } finally { setBusy(null); }
  }

  function exportBrief() {
    if (!brief) return;
    const sections = [
      `# ${brief.title}`, brief.overview, `Generated: ${brief.generated_at}`,
      "## Saved research answers",
      ...brief.saved_answers.map((item) => `### ${item.question}\n\n${item.direct_answer || item.short_answer}\n\n${item.generation_note || ""}\n\n${item.uncertainty.join("\n")}`),
      "## Evidence gaps", ...brief.evidence_gaps.map((item) => `- ${item}`),
      "## Next steps", ...brief.next_steps.map((item) => `- ${item}`),
      "## Sources", ...brief.citations.map((citation) => {
        const source = extractions.find((row) => row.citation === citation);
        return `- ${citation}${source?.source_url ? ` — ${source.source_url}` : ""}`;
      }), brief.safety_note,
    ];
    const url = URL.createObjectURL(new Blob([sections.join("\n\n")], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = "triallens-research-brief.md"; link.click();
    URL.revokeObjectURL(url);
  }

  async function markRow(row: EvidenceExtraction, reviewStatus: EvidenceExtraction["review_status"]) {
    if (!workspace || busy) return;
    setBusy("Saving review");
    setError(null);
    try {
      const updated = await api.updateExtraction(workspace.id, row.id, reviewStatus);
      setExtractions((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedRow(updated);
      setBrief(await api.brief(workspace.id));
    } catch (err) {
      setError(workspaceErrorMessage(err, "Could not save the review. Try again."));
    } finally { setBusy(null); }
  }

  function clearEvidenceFilters() {
    setSourceFilter("all");
    setReviewFilter("all");
    setQuantOnly(false);
  }

  function selectWorkspaceTab(tab: WorkspaceTab) {
    setActiveTab(tab);
    scrollToWorkspace();
  }

  return (
    <main className="triallens-shell min-h-screen overflow-x-clip">
      <FixedInstrumentationHeader
        activeTab={activeTab}
        busy={busy}
        extractionCount={extractions.length}
        needsReviewCount={needsReviewCount}
        onNavigate={selectWorkspaceTab}
        sourceCount={totalSources}
        workflowStatus={workflowStatus}
      />

      <section id="home" className="evidence-intro relative overflow-hidden">
        <HeroParallaxScene />
        <div className="evidence-intro-grid relative z-10 mx-auto grid w-full max-w-[1480px] gap-8 px-5 md:px-8 lg:grid-cols-[minmax(0,0.78fr)_minmax(420px,1.22fr)] lg:items-center lg:px-10">
          <HeroCopy />
          <WorkspaceLauncher
            busy={busy}
            condition={condition}
            error={error}
            intervention={intervention}
            recentWorkspaces={recentWorkspaces}
            onBuildWorkspace={buildWorkspace}
            onConditionChange={setCondition}
            onInterventionChange={setIntervention}
            onReopenWorkspace={reopenWorkspace}
          />
        </div>
      </section>

      <FieldBridge counts={counts} extractionCount={extractions.length} sourceCount={totalSources} />

      <section id="workspace" className="workspace-section relative px-4 pb-16 sm:px-5 md:px-8 lg:px-10">
        <motion.div
          className="workspace-frame relative z-10 mx-auto max-w-[1480px]"
          initial={{ opacity: 0.94, clipPath: "inset(0 0 8% 0 round 18px)" }}
          whileInView={{ opacity: 1, clipPath: "inset(0 0 0% 0 round 18px)" }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.56, ease: [0.16, 1, 0.3, 1] }}
        >
        <Tabs value={activeTab} onValueChange={(value) => selectWorkspaceTab(value as WorkspaceTab)} orientation="vertical" className="workspace-shell">
          <TabsList className="workspace-rail" aria-label="Workspace views">
            <TabsTrigger value="table" className="workspace-rail-item"><Filter /> Evidence</TabsTrigger>
            <TabsTrigger id="ask" value="ask" className="workspace-rail-item"><MessageSquareText /> Ask</TabsTrigger>
            <TabsTrigger id="sources" value="sources" className="workspace-rail-item"><BookOpen /> Sources</TabsTrigger>
            <TabsTrigger value="brief" className="workspace-rail-item"><FlaskConical /> Brief</TabsTrigger>
            <TabsTrigger value="reliability" className="workspace-rail-item"><Activity /> Reliability</TabsTrigger>
          </TabsList>

          <TabsContent value="table" className="w-full">
            <Card className="paper-panel rounded-sm border-0 bg-transparent">
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="flex items-center gap-2 font-display text-4xl tracking-[-0.04em] md:text-5xl">
                  <Filter data-icon="inline-start" /> Evidence extraction table
                </CardTitle>
                <CardDescription className="text-ink/68">
                  Each row is a source-level extraction. Use Inspect for the supporting quote, extracted fields, and original source.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <EvidenceFilters
                  sourceFilter={sourceFilter}
                  reviewFilter={reviewFilter}
                  quantOnly={quantOnly}
                  setSourceFilter={setSourceFilter}
                  setReviewFilter={setReviewFilter}
                  setQuantOnly={setQuantOnly}
                />
                {busy && !extractions.length ? (
                  <LoadingRows />
                ) : !extractions.length ? (
                  <Alert>
                    <Search data-icon="inline-start" />
                    <AlertTitle>No extraction table yet</AlertTitle>
                    <AlertDescription>Create a workspace to retrieve sources and extract structured evidence rows.</AlertDescription>
                  </Alert>
                ) : filteredExtractions.length === 0 ? (
                  <Alert className="border-ink/15 bg-paper/80 text-ink">
                    <Filter data-icon="inline-start" />
                    <AlertTitle>No rows match these filters</AlertTitle>
                    <AlertDescription className="flex flex-col gap-3 text-ink/68">
                      <span>Try a broader source type, include all review states, or turn off the quantitative-result filter.</span>
                      <Button type="button" variant="outline" size="sm" className="w-fit rounded-sm" onClick={clearEvidenceFilters}>
                        Clear filters
                      </Button>
                    </AlertDescription>
                  </Alert>
                ) : (
                  <>
                    <p className="table-scroll-hint">
                      <ArrowLeftRight aria-hidden="true" /> Scroll sideways to see review status and row actions.
                    </p>
                    <EvidenceTable rows={visibleExtractions} onInspect={setSelectedRow} onReview={markRow} />
                    {hiddenExtractionCount > 0 || showAllRows ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="self-start rounded-sm"
                        onClick={() => setShowAllRows((value) => !value)}
                      >
                        {showAllRows ? "Show fewer rows" : `See ${hiddenExtractionCount} more rows`}
                      </Button>
                    ) : null}
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="ask" className="w-full">
            <Card className="paper-panel rounded-sm border-0 bg-transparent text-ink">
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="font-display text-4xl tracking-[-0.04em] md:text-5xl">Ask the evidence.</CardTitle>
                <CardDescription className="max-w-3xl text-ink/68">
                  Explore a question, follow the reasoning, and check the sources. Save useful answers to your research brief.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {!isReady && (
                  <Alert className="border-ink/10 bg-paper/70 text-ink">
                    <AlertTitle>Build a workspace first</AlertTitle>
                    <AlertDescription className="text-ink/68">Once extraction rows exist, this panel becomes a cited synthesis interface.</AlertDescription>
                  </Alert>
                )}
                {isReady && !answer && (
                  <div className="flex flex-wrap gap-2" aria-label="Suggested questions">
                    {suggestedQuestions.map((item) => (
                      <Button key={item} type="button" size="sm" variant="outline" className="rounded-sm border-ink/15 bg-paper/70 text-ink hover:border-moss hover:bg-fog" onClick={() => setQuestion(item)}>
                        {item}
                      </Button>
                    ))}
                  </div>
                )}
                {usage && <div className="text-sm text-ink/68" role={usage.answer_alert || usage.budget_exhausted ? "alert" : "status"}>
                  <p>{usage.generated_answers} / {usage.answer_alert_at} generated answers · US${usage.used_or_reserved_usd.toFixed(4)} used or reserved of US${usage.budget_usd.toFixed(2)}</p>
                  {usage.answer_alert && <p>You’ve reached {usage.answer_alert_at} generated answers. Review your usage before continuing.</p>}
                  {usage.budget_exhausted && <p>Your spending cap has been reached. Paid generation is paused.</p>}
                  {usage.pending_requests > 0 && <p>Includes reserved cost for requests with unconfirmed usage.</p>}
                </div>}
                {isReady && <div className="conversation-toolbar">
                  <p>{workspace?.condition}{workspace?.intervention ? ` / ${workspace.intervention}` : ""}</p>
                  <label>Sources
                    <select aria-label="Sources for this conversation" value={askFilter} disabled={Boolean(busy)} onChange={(event) => { setAskFilter(event.target.value as SourceType | "all"); setAnswer(null); }}>
                      {sourceFilterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <Button variant="outline" size="sm" disabled={Boolean(busy) || !answer} onClick={() => { setAnswer(null); setQuestion(""); }}>New conversation</Button>
                </div>}
                {conversation.filter((item) => item.id !== answer?.id).map((item) => (
                  <details className="conversation-turn" key={item.id}>
                    <summary>{item.question}<ChevronDown aria-hidden="true" /></summary>
                    <CitedAnswerText text={item.direct_answer || item.short_answer} citations={item.citations} extractions={extractions} retrievedChunks={item.retrieved_chunks} />
                    <p className="text-sm text-ink/68">{item.generation_note}</p>
                    <Button variant="outline" size="sm" disabled={Boolean(busy)} onClick={() => { setAskFilter(item.source_types?.[0] ?? "all"); setAnswer(item); setQuestion(""); }}>Continue conversation</Button>
                    <Button variant="outline" size="sm" disabled={Boolean(busy)} onClick={() => saveToBrief(item, !item.saved_to_brief)}>{item.saved_to_brief ? "Remove from brief" : "Save to brief"}</Button>
                  </details>
                ))}
                {answer && <>
                  <AnswerPanel answer={answer} extractions={extractions} onInspect={setSelectedRow} />
                  <div><Button variant="outline" disabled={Boolean(busy)} onClick={() => saveToBrief(answer, !answer.saved_to_brief)}>{answer.saved_to_brief ? "Remove from brief" : "Save to brief"}</Button></div>
                </>}
                {busy === "Synthesizing from evidence table" && <p role="status" className="text-sm text-ink/68">Reading sources and preparing your answer…</p>}
                <div className="ask-composer">
                  <label htmlFor="ask-question" className="flex flex-col gap-2 text-sm font-semibold text-ink">
                    {answer ? "Ask a follow-up" : "Research question"}
                    <Textarea
                      id="ask-question"
                      value={question}
                      onChange={(event) => setQuestion(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                          event.preventDefault();
                          void ask();
                        }
                      }}
                      className="min-h-24 border-ink/15 bg-paper text-ink"
                      placeholder={answer ? "Ask for a comparison, limitation, statistic, or source detail" : "Ask about benefits, risks, study quality, or uncertainty"}
                    />
                  </label>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-ink/62">
                      {askFilter === "all" ? "Searching all indexed sources" : `Searching ${sourceLabels[askFilter]}`} · Ctrl/⌘ + Enter to ask
                    </p>
                    <Button onClick={ask} disabled={!isReady || Boolean(busy) || question.trim().length < 3} className="rounded-sm bg-ink text-paper hover:bg-moss">
                      <MessageSquareText data-icon="inline-start" /> {answer ? "Ask follow-up" : "Answer with citations"}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sources" className="w-full">
            <Card className="paper-panel rounded-sm border-0 bg-transparent">
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="flex items-center gap-2 font-display text-4xl tracking-[-0.04em] md:text-5xl">
                  <BookOpen data-icon="inline-start" /> Source explorer
                </CardTitle>
                <CardDescription className="text-ink/68">Inspect normalized source records and open original PubMed, ClinicalTrials.gov, or FDA pages.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {sources.length === 0 && <p className="text-ink/65">Build a workspace to inspect normalized biomedical sources.</p>}
                  {visibleSources.map((source) => (
                    <article key={source.id} className="source-card p-4 transition hover:-translate-y-0.5">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{sourceLabels[source.source_type]}</Badge>
                        {source.phase && <Badge variant="outline">{source.phase}</Badge>}
                        {source.status && <Badge variant="outline">{source.status}</Badge>}
                      </div>
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="font-semibold">{source.title}</h3>
                        {source.url ? (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg border border-border bg-background px-2.5 text-[0.8rem] font-medium text-foreground transition hover:bg-muted"
                          >
                            Open <ExternalLink data-icon="inline-end" />
                          </a>
                        ) : null}
                      </div>
                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-ink/70">{source.abstract}</p>
                      {source.source_type === "fda_adverse_event" && (
                        <p className="mt-2 rounded-sm bg-signal/10 px-2 py-1.5 text-xs leading-5 text-ink/68">
                          Reported signal, not proof of causation.
                        </p>
                      )}
                    </article>
                  ))}
                </div>
                {hiddenSourceCount > 0 || showAllSources ? (
                  <Button type="button" variant="outline" className="mt-4 rounded-sm" onClick={() => setShowAllSources((value) => !value)}>
                    {showAllSources ? "Show fewer sources" : `See ${hiddenSourceCount} more sources`}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="brief" className="w-full">
            <Card className="paper-panel rounded-sm border-0 bg-transparent">
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="flex items-center gap-2 font-display text-4xl tracking-[-0.04em] md:text-5xl">
                  <FlaskConical data-icon="inline-start" /> Evidence brief
                </CardTitle>
                <CardDescription className="text-ink/68">Collect the answers worth keeping, check outstanding evidence gaps, and export a research handoff.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm leading-6">
                {brief ? (
                  <article className="brief-layout">
                    <div><Button variant="outline" onClick={exportBrief} disabled={!brief.saved_answers?.length}>Export brief</Button></div>
                    <section className="brief-overview" aria-labelledby="brief-overview-title">
                      <h3 id="brief-overview-title">Overview</h3>
                      <p>{brief.overview}</p>
                      <dl className="brief-source-counts">
                        {Object.entries(brief.source_summary).map(([source, count]) => (
                          <div key={source}>
                            <dt>{sourceLabels[source as SourceType] ?? source.replaceAll("_", " ")}</dt>
                            <dd>{count}</dd>
                          </div>
                        ))}
                      </dl>
                    </section>
                    <section className="brief-section" aria-labelledby="brief-findings-title">
                      <h3 id="brief-findings-title">Saved research answers</h3>
                      {brief.saved_answers?.length ? brief.saved_answers.map((item) => (
                        <section className="brief-saved-answer" key={item.id}>
                          <h4>{item.question}</h4>
                          <CitedAnswerText text={item.direct_answer || item.short_answer} citations={item.citations} extractions={extractions} retrievedChunks={item.retrieved_chunks} />
                          <p className="text-sm text-ink/68">{item.generation_note}</p>
                          {item.uncertainty.length > 0 && <ul>{item.uncertainty.map((note) => <li key={note}>{note}</li>)}</ul>}
                          <Button variant="outline" size="sm" disabled={Boolean(busy)} onClick={() => saveToBrief(item, false)}>Remove from brief</Button>
                        </section>
                      )) : <div className="brief-empty"><p>No answers saved yet. Use Ask to explore the evidence, then save answers that help your research question.</p><Button variant="outline" onClick={() => selectWorkspaceTab("ask")}>Ask a research question</Button></div>}
                    </section>
                    <section className="brief-section"><h3>Next steps</h3><ul>{brief.next_steps?.map((step) => <li key={step}>{step}</li>)}</ul></section>
                    <div className="brief-split">
                      <section className="brief-section" aria-labelledby="brief-gaps-title">
                        <h3 id="brief-gaps-title">Evidence gaps</h3>
                        {brief.evidence_gaps.length ? (
                          <ul>{brief.evidence_gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>
                        ) : <p>No additional evidence gaps were identified.</p>}
                      </section>
                      <section className="brief-safety" aria-labelledby="brief-safety-title">
                        <h3 id="brief-safety-title"><CircleAlert aria-hidden="true" /> Safety note</h3>
                        <p>{brief.safety_note}</p>
                      </section>
                    </div>
                    {brief.citations.length ? (
                      <details className="answer-disclosure">
                        <summary><span>Citations</span><span>{brief.citations.length} sources</span><ChevronDown aria-hidden="true" /></summary>
                        <ul className="disclosure-list">{brief.citations.map((citation) => <li key={citation}>{citation}</li>)}</ul>
                      </details>
                    ) : null}
                  </article>
                ) : (
                  <p className="text-ink/65">A generated brief appears after ingestion.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="reliability" className="w-full">
            <Card className="paper-panel rounded-sm border-0 bg-transparent">
              <CardHeader>
                <CardTitle role="heading" aria-level={2} className="flex items-center gap-2 font-display text-4xl tracking-[-0.04em] md:text-5xl">
                  <Activity data-icon="inline-start" /> Reliability checks
                </CardTitle>
                <CardDescription className="text-ink/68">Human-readable checks for retrieval, extraction coverage, citation support, and abstention.</CardDescription>
              </CardHeader>
              <CardContent>
                {evals ? (
                  <div className="reliability-layout">
                    <p className="reliability-note">These are illustrative development targets, not measured scores for this workspace. Live evaluation has not run. They do not establish clinical validity.</p>
                    <section className="reliability-metrics" aria-label="Reliability metrics">
                      {evals.metrics.map((metric) => {
                        const score = Math.round(metric.score * 100);
                        return (
                          <article key={metric.name} className="reliability-metric">
                            <div>
                              <h3>{metric.name.replaceAll("_", " ")}</h3>
                              <strong>Target {score}%</strong>
                            </div>
                            <div className="metric-track" role="progressbar" aria-label={metric.name.replaceAll("_", " ")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={score}>
                              <span style={{ "--metric-score": `${score}%` } as CSSProperties} />
                            </div>
                            <p>{metric.description}</p>
                          </article>
                        );
                      })}
                    </section>
                    <section className="reliability-scenarios" aria-labelledby="scenario-checks-title">
                      <h3 id="scenario-checks-title">Scenario checks</h3>
                      <div>
                        {evals.scenarios.map((scenario) => {
                          const passed = scenario.status.toLowerCase().includes("pass");
                          return (
                            <article key={scenario.name}>
                              {passed ? <CheckCircle2 aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
                              <div>
                                <h4>{scenario.name}</h4>
                                <p>{scenario.question}</p>
                                <small>Expected: {scenario.expected}</small>
                              </div>
                              <Badge variant={passed ? "secondary" : "outline"}>{scenario.status}</Badge>
                            </article>
                          );
                        })}
                      </div>
                    </section>
                    <div className="reliability-active"><CheckCircle2 aria-hidden="true" /> Extraction-first checks active</div>
                  </div>
                ) : (
                  <p className="text-ink/65">Evaluation results appear after workspace creation.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        </motion.div>
      </section>

      <CitationSheet row={selectedRow} onOpenChange={(open) => !open && setSelectedRow(null)} onReview={markRow} />
    </main>
  );
}

function readCachedWorkspaces(): Workspace[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_WORKSPACES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, 4) : [];
  } catch {
    return [];
  }
}

function writeCachedWorkspaces(items: Workspace[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(RECENT_WORKSPACES_KEY, JSON.stringify(items.slice(0, 4)));
  } catch {
    // Local storage is only a convenience cache.
  }
}

function mergeRecentWorkspaces(primary: Workspace[], secondary: Workspace[]) {
  const byKey = new Map<string, Workspace>();
  for (const item of [...primary, ...secondary]) {
    byKey.set(`${item.condition.toLowerCase()}::${item.intervention?.toLowerCase() ?? ""}`, item);
  }
  return Array.from(byKey.values()).slice(0, 4);
}

function workspaceErrorMessage(err: unknown, fallback = "Something went wrong while building the workspace.") {
  const message = err instanceof Error ? err.message : fallback;
  if (message === "Failed to fetch" || message.includes("fetch failed")) {
    return "Could not reach the TrialLens API at http://localhost:8000. Start the FastAPI backend, then create the workspace again.";
  }
  return message || fallback;
}

function scrollToWorkspace() {
  window.requestAnimationFrame(() => {
    const workspace = document.querySelector("#workspace");
    if (!workspace) return;
    const top = workspace.getBoundingClientRect().top + window.scrollY - 88;
    window.scrollTo({ top: Math.max(top, 0), behavior: preferredScrollBehavior() });
    window.setTimeout(() => {
      if (window.scrollY < 80) {
        window.location.hash = "workspace";
      }
    }, 350);
  });
}

function preferredScrollBehavior(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

function FixedInstrumentationHeader({
  activeTab,
  busy,
  extractionCount,
  needsReviewCount,
  onNavigate,
  sourceCount,
  workflowStatus,
}: {
  activeTab: WorkspaceTab;
  busy: string | null;
  extractionCount: number;
  needsReviewCount: number;
  onNavigate: (tab: WorkspaceTab) => void;
  sourceCount: number;
  workflowStatus: WorkflowStatus;
}) {
  return (
    <header className="field-header">
      <div className="field-header-inner">
        <a href="#home" className="field-brand" aria-label="TrialLens home">
          <span className="field-brand-mark" aria-hidden="true">
            <FileSearch />
          </span>
          <span>TrialLens</span>
        </a>

        <nav className="field-nav" aria-label="Primary">
          {navItems.map((item) => (
            <a
              key={item.href}
              className="nav-link"
              href={item.href}
              aria-current={activeTab === item.tab ? "page" : undefined}
              onClick={() => onNavigate(item.tab)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="header-utilities">
          <div className="workspace-readout" aria-live="polite">
            <span>{busy ?? workflowStatus}</span>
            <span>{sourceCount} sources</span>
            <span>{extractionCount} rows</span>
            {needsReviewCount > 0 ? <span>{needsReviewCount} to review</span> : null}
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = window.localStorage.getItem("triallens.theme");
    const next = saved === "dark" || saved === "light"
      ? saved
      : document.documentElement.classList.contains("dark") || window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    document.documentElement.classList.toggle("dark", next === "dark");
    document.documentElement.classList.toggle("light", next === "light");
    document.cookie = `triallens.theme=${next}; path=/; max-age=31536000; samesite=lax`;
    setTheme(next);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    document.documentElement.classList.toggle("light", next === "light");
    window.localStorage.setItem("triallens.theme", next);
    document.cookie = `triallens.theme=${next}; path=/; max-age=31536000; samesite=lax`;
    setTheme(next);
  }

  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={`Switch to ${nextTheme} mode`}
      aria-pressed={theme === "dark"}
      title={`Switch to ${nextTheme} mode`}
    >
      <Sun className="theme-icon theme-icon-sun" aria-hidden="true" />
      <Moon className="theme-icon theme-icon-moon" aria-hidden="true" />
    </button>
  );
}

function HeroParallaxScene() {
  return (
    <div className="evidence-flow-scene pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="flow-zone flow-zone-copy" />
      <div className="flow-zone flow-zone-form" />
      <div className="flow-zone flow-zone-workspace" />
      <div className="source-streams">
        {(Object.entries(sourceLabels) as [SourceType, string][]).map(([key, label], index) => (
          <div key={key} className="source-stream" style={{ "--stream-index": index } as CSSProperties}>
            <span>{label}</span>
            <i />
          </div>
        ))}
      </div>
      <div className="evidence-spine" />
    </div>
  );
}

function HeroCopy() {
  return (
    <div className="hero-copy">
      <h1 className="hero-title font-display">
        Follow the <span>evidence.</span>
      </h1>
      <p className="hero-subtitle">Gather biomedical sources, explore what they mean, and keep every research answer connected to its evidence.</p>
      <p className="scope-note">Evidence navigation only. Not medical advice or clinical decision support.</p>
    </div>
  );
}

function WorkspaceLauncher({
  busy,
  condition,
  error,
  intervention,
  recentWorkspaces,
  onBuildWorkspace,
  onConditionChange,
  onInterventionChange,
  onReopenWorkspace,
}: {
  busy: string | null;
  condition: string;
  error: string | null;
  intervention: string;
  recentWorkspaces: Workspace[];
  onBuildWorkspace: (event?: FormEvent) => void;
  onConditionChange: (value: string) => void;
  onInterventionChange: (value: string) => void;
  onReopenWorkspace: (workspace: Workspace) => void;
}) {
  return (
    <form onSubmit={onBuildWorkspace} className="hero-launcher">
      <div className="launcher-heading">
        <h2>Build a workspace</h2>
        <p>Choose a condition and optional intervention. TrialLens gathers sources and extracts inspectable rows.</p>
      </div>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>Workspace issue</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="launcher-fields">
        <label htmlFor="condition" className="launcher-field">
          <span>Condition</span>
          <Input
            id="condition"
            value={condition}
            onChange={(event) => onConditionChange(event.target.value)}
            className="launcher-input"
            placeholder="e.g. type 2 diabetes"
          />
        </label>
        <label htmlFor="intervention" className="launcher-field">
          <span>Drug or intervention</span>
          <Input
            id="intervention"
            value={intervention}
            onChange={(event) => onInterventionChange(event.target.value)}
            className="launcher-input"
            placeholder="e.g. metformin"
          />
        </label>
        <Button
          type="submit"
          disabled={Boolean(busy)}
          size="lg"
          className="build-workspace-button"
        >
          {busy ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
          <span>{busy ?? "Build workspace"}</span>
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
      {recentWorkspaces.length > 0 && (
        <div className="recent-workspaces">
          <h3>Recent workspaces</h3>
          <div className="recent-workspace-list">
            {recentWorkspaces.map((item) => (
              <Button
                key={item.id}
                type="button"
                variant="outline"
                className="recent-workspace-button"
                onClick={() => onReopenWorkspace(item)}
              >
                <span className="text-left">
                  <span className="font-semibold">{item.condition}</span>
                  {item.intervention ? <span> + {item.intervention}</span> : null}
                </span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}

function FieldBridge({
  counts,
  extractionCount,
  sourceCount,
}: {
  counts: Record<string, number>;
  extractionCount: number;
  sourceCount: number;
}) {
  return (
    <section className="provenance-band" aria-labelledby="provenance-title">
      <div className="provenance-inner">
        <div className="provenance-heading">
          <h2 id="provenance-title">Four source families. One inspectable path.</h2>
          <p>Source records become structured rows before synthesis.</p>
        </div>
        <div className="provenance-sources" aria-label="Current evidence inventory">
          {(Object.entries(sourceLabels) as [SourceType, string][]).map(([key, label]) => (
            <div key={key} className="provenance-source">
              <span>{label}</span>
              <strong>{counts[key] ?? 0}</strong>
            </div>
          ))}
        </div>
        <div className="provenance-totals">
          <span><strong>{sourceCount}</strong> sources</span>
          <span><strong>{extractionCount}</strong> rows</span>
        </div>
      </div>
    </section>
  );
}

function workflowStateFromCounts(sourceCount: number, extractionCount: number, rows: EvidenceExtraction[]): WorkflowStatus {
  if (!sourceCount) return "limited evidence";
  if (!extractionCount) return "extracting fields";
  if (rows.some((row) => row.review_status === "needs_review")) return "needs review";
  return "ready for synthesis";
}

function EvidenceFilters({
  sourceFilter,
  reviewFilter,
  quantOnly,
  setSourceFilter,
  setReviewFilter,
  setQuantOnly,
}: {
  sourceFilter: SourceType | "all";
  reviewFilter: "all" | "reviewed" | "unreviewed" | "needs_review";
  quantOnly: boolean;
  setSourceFilter: (value: SourceType | "all") => void;
  setReviewFilter: (value: "all" | "reviewed" | "unreviewed" | "needs_review") => void;
  setQuantOnly: (value: boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-sm border border-ink/10 bg-paper/60 p-3">
      <div>
        <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-ink/68">Source type</p>
        <div className="flex flex-wrap gap-1.5">
        {sourceFilterOptions.map((option) => (
          <FilterButton
            key={option.value}
            active={sourceFilter === option.value}
            label={`Source filter: ${option.label}`}
            testId={`source-filter-${option.value}`}
            onClick={() => setSourceFilter(option.value)}
          >
            {option.label}
          </FilterButton>
        ))}
        </div>
      </div>
      <div>
        <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink/68">Review state</p>
        <p className="mb-2 text-xs leading-5 text-ink/62">
          Use "Mark checked" on a study row after you inspect it. Low confidence means TrialLens thinks the extraction needs human review.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {[
            { label: "Any status", value: "all" },
            { label: "Checked", value: "reviewed" },
            { label: "Not checked", value: "unreviewed" },
            { label: "Low confidence", value: "needs_review" },
          ].map((item) => (
            <FilterButton
              key={item.value}
              active={reviewFilter === item.value}
              label={`Review filter: ${item.label}`}
              testId={`review-filter-${item.value}`}
              onClick={() => setReviewFilter(item.value as "all" | "reviewed" | "unreviewed" | "needs_review")}
            >
              {item.label}
            </FilterButton>
          ))}
          <FilterButton active={quantOnly} label="Filter: only rows with numbers" testId="filter-quantitative" onClick={() => setQuantOnly(!quantOnly)}>
            Only rows with numbers
          </FilterButton>
        </div>
      </div>
    </div>
  );
}

function FilterButton({
  active,
  children,
  label,
  testId,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  label: string;
  testId: string;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      aria-label={label}
      aria-pressed={active}
      data-testid={testId}
      className={cn(
        "h-7 rounded-sm border-ink/15 px-2.5 text-xs font-semibold transition",
        active ? "border-ink bg-ink text-paper shadow-sm hover:bg-ink/90 hover:text-paper" : "bg-paper/75 text-ink/70 hover:border-moss/60 hover:bg-paper hover:text-ink"
      )}
      onClick={onClick}
    >
      {active && <CheckCircle2 data-icon="inline-start" />}
      {children}
    </Button>
  );
}

function EvidenceTable({
  rows,
  onInspect,
  onReview,
}: {
  rows: EvidenceExtraction[];
  onInspect: (row: EvidenceExtraction) => void;
  onReview: (row: EvidenceExtraction, status: EvidenceExtraction["review_status"]) => void;
}) {
  return (
    <Table className="min-w-full table-fixed">
      <TableHeader>
        <TableRow>
          <TableHead className="w-[34%] text-ink/70">Source</TableHead>
          <TableHead className="w-[38%] text-ink/70">Result snapshot</TableHead>
          <TableHead className="w-[14%] text-ink/70">Review</TableHead>
          <TableHead className="w-[14%] text-ink/70">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id} className="align-top">
            <TableCell className="whitespace-normal align-top">
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary">{sourceLabels[row.source_type]}</Badge>
                  {row.status && <Badge variant="outline">{row.status}</Badge>}
                  {row.phase && <Badge variant="outline">{row.phase}</Badge>}
                  {row.has_quantitative_result && <Badge>quant</Badge>}
                </div>
                <span className="line-clamp-2 font-semibold leading-5">{row.title}</span>
                <span className="break-words text-xs text-ink/68">{row.citation}</span>
              </div>
            </TableCell>
            <TableCell className="whitespace-normal align-top text-ink/78">
              <p className="line-clamp-3 leading-6">{fieldValue(row.outcome_result, row.supporting_quote, row.supporting_quote)}</p>
              {compactSafetyNote(row) ? <p className="mt-2 line-clamp-1 text-xs text-signal/80">Safety: {compactSafetyNote(row)}</p> : null}
            </TableCell>
            <TableCell className="whitespace-normal align-top text-ink/72">
              <div className="flex flex-wrap items-center gap-1.5">
                <Tooltip>
                  <TooltipTrigger render={<Badge variant={row.review_status === "needs_review" ? "destructive" : "outline"} />}>
                    {Math.round(row.confidence * 100)}%
                  </TooltipTrigger>
                  <TooltipContent>Review status: {row.review_status.replace("_", " ")}</TooltipContent>
                </Tooltip>
                {row.review_status === "reviewed" ? (
                  <Badge className="bg-moss text-paper">Checked</Badge>
                ) : (
                  <Button type="button" size="xs" variant="outline" className="h-6 rounded-sm bg-paper/75 px-2 text-xs" onClick={() => onReview(row, "reviewed")}>
                    Mark checked
                  </Button>
                )}
              </div>
            </TableCell>
            <TableCell className="whitespace-normal align-top">
              <div className="flex max-w-full flex-col items-start gap-1.5">
                <Button type="button" size="sm" variant="outline" className="h-7 rounded-sm text-moss" onClick={() => onInspect(row)}>
                  Inspect
                </Button>
                {row.source_url ? (
                  <a
                    href={row.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-7 max-w-full items-center gap-1 rounded-sm border border-ink/15 bg-paper px-2 text-[0.8rem] font-semibold text-ink transition hover:border-moss hover:bg-fog"
                  >
                    <span>Open source</span>
                    <ExternalLink className="size-3.5 shrink-0" data-icon="inline-end" />
                  </a>
                ) : (
                  <span className="inline-flex rounded-sm border border-ink/10 px-2 py-1 text-xs text-ink/68">No source link</span>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AnswerPanel({
  answer,
  extractions,
  onInspect,
}: {
  answer: Answer;
  extractions: EvidenceExtraction[];
  onInspect: (row: EvidenceExtraction) => void;
}) {
  const facetCoverage = safeList(answer.facet_coverage);
  const evidenceMap = safeList(answer.evidence_map);
  const reasoningSummary = safeList(answer.reasoning_summary);
  const evidenceSynthesis = safeList(answer.evidence_synthesis);
  const evidenceQuality = safeList(answer.evidence_quality);
  const sourceReadouts = safeList(answer.source_readouts);
  const answerTrace = safeList(answer.answer_trace);
  const supportingEvidence = safeList(answer.supporting_evidence);
  const evidence = safeList(answer.evidence);
  const safetyLimitations = safeList(answer.safety_limitations);
  const uncertainty = safeList(answer.uncertainty);
  const citations = safeList(answer.citations);
  const retrievedChunks = safeList(answer.retrieved_chunks);
  const caveats = Array.from(new Set([...uncertainty, ...safetyLimitations])).slice(0, 1);
  const answerMethodCount = answerTrace.length + facetCoverage.length + evidenceQuality.length + evidenceMap.length + reasoningSummary.length;

  return (
    <motion.section
      id="answer-result"
      tabIndex={-1}
      aria-labelledby="answer-result-title"
      className="answer-result"
      initial={{ opacity: 0.82, clipPath: "inset(0 0 10% 0 round 14px)" }}
      animate={{ opacity: 1, clipPath: "inset(0 0 0% 0 round 14px)" }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
    >
      <header className="answer-result-heading">
        <div>
          <h3 id="answer-result-title">{answer.question}</h3>
        </div>
        <div className="answer-result-meta" aria-label={`${citations.length} citations and ${retrievedChunks.length} retrieved passages`}>
          <span>{citations.length} citations</span>
          <span>{retrievedChunks.length} passages</span>
        </div>
      </header>

      {answer.generation_note && <p className="answer-generation-note" role="status">{answer.generation_note}</p>}
      <CitedAnswerText
        text={answer.direct_answer || answer.short_answer}
        citations={citations}
        extractions={extractions}
        retrievedChunks={retrievedChunks}
      />

      <div className="answer-boundary">
        <section aria-labelledby="answer-boundary-title">
          <h4 id="answer-boundary-title"><CircleAlert aria-hidden="true" /> Evidence boundary</h4>
          <p>{caveats[0] || "No additional uncertainty note was returned for this answer."}</p>
        </section>
      </div>

      {citations.length ? (
        <section className="answer-citations" aria-labelledby="answer-citations-title">
          <h4 id="answer-citations-title">Sources cited in this answer</h4>
          <div>
            {citations.map((citation, index) => {
              const row = extractions.find((item) => item.citation === citation);
              const chunk = retrievedChunks.find((item) => item.citation === citation);
              const meta = citationMeta(citation, row, chunk);
              return (
                <div id={`answer-citation-${index + 1}`} className="answer-citation-item" key={citation}>
                  {meta.url ? (
                    <a href={meta.url} target="_blank" rel="noreferrer" aria-label={`${meta.url?.includes("open.fda.gov/apis/") ? "Open source documentation" : "Open original source"}: ${meta.displayLabel}`}>
                      <span>[{index + 1}] {meta.displayLabel}</span>
                      <ExternalLink aria-hidden="true" />
                    </a>
                  ) : (
                    <span>[{index + 1}] {meta.displayLabel}</span>
                  )}
                  {row ? (
                    <button type="button" onClick={() => onInspect(row)} aria-label={`Inspect extracted evidence for ${meta.displayLabel}`}>
                      Inspect evidence
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      <div className="answer-details" aria-label="Detailed answer evidence">
        <AnswerDisclosure title="Supporting evidence" meta={`${supportingEvidence.length + evidenceSynthesis.length + evidence.length} items`}>
          <AnswerList title="Cross-source synthesis" items={evidenceSynthesis} />
          <AnswerList title="Supporting evidence" items={supportingEvidence.length ? supportingEvidence : evidence} />
          <AnswerList title="Safety or limitations" items={safetyLimitations} />
          <AnswerList title="What remains uncertain" items={uncertainty} />
          {citations.length > 4 ? <AnswerList title="All citations" items={citations} /> : null}
        </AnswerDisclosure>

        {answerMethodCount ? (
          <AnswerDisclosure title="How this answer was built" meta={`${answerMethodCount} checks`}>
            {answerTrace.length ? <AnswerTrace items={answerTrace} /> : null}
            <AnswerList title="Question coverage" items={facetCoverage} />
            <AnswerList title="Evidence quality" items={evidenceQuality} />
            <AnswerList title="Workspace evidence map" items={evidenceMap} />
            <AnswerList title="Reasoning notes" items={reasoningSummary} />
          </AnswerDisclosure>
        ) : null}

        {retrievedChunks.length ? (
          <AnswerDisclosure title="Source-by-source readout" meta={`${retrievedChunks.length} passages`}>
            <div className="retrieved-passages">
              {retrievedChunks.map((chunk) => (
                <article key={chunk.chunk_id}>
                  <div>
                    <span>{sourceLabels[chunk.source_type]}</span>
                    <Badge variant="secondary">{Math.round(chunk.score * 100)}% match</Badge>
                  </div>
                  <h5>{chunk.title || chunk.citation}</h5>
                  <p className="passage-citation">{chunk.citation}</p>
                  {chunk.matched_terms.length ? <p>{chunk.relevance_note}</p> : null}
                  <blockquote>{chunk.text}</blockquote>
                  {chunk.url ? <a href={chunk.url} target="_blank" rel="noreferrer">Open source <ExternalLink aria-hidden="true" /></a> : null}
                </article>
              ))}
            </div>
          </AnswerDisclosure>
        ) : null}

        {sourceReadouts.length ? (
          <AnswerDisclosure title="Source matching notes" meta={`${sourceReadouts.length} notes`}>
            <AnswerList title="Source readout" items={sourceReadouts} />
          </AnswerDisclosure>
        ) : null}
      </div>
    </motion.section>
  );
}

function CitedAnswerText({
  text,
  citations,
  extractions,
  retrievedChunks,
}: {
  text: string;
  citations: string[];
  extractions: EvidenceExtraction[];
  retrievedChunks: RetrievedChunk[];
}) {
  const parts: ReactNode[] = [];
  const markerPattern = /\[([^\]]+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = markerPattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const citation = match[1];
    const citationIndex = citations.indexOf(citation);
    const row = extractions.find((item) => item.citation === citation);
    const chunk = retrievedChunks.find((item) => item.citation === citation);
    const meta = citationMeta(citation, row, chunk);
    if (citationIndex >= 0) {
      parts.push(
        meta.url ? (
          <a key={`${citation}-${match.index}`} className="inline-citation" href={meta.url} target="_blank" rel="noreferrer" aria-label={`${meta.url?.includes("open.fda.gov/apis/") ? "Open source documentation" : "Open cited source"}: ${meta.displayLabel}`}>
            ({meta.inlineLabel})
          </a>
        ) : (
          <span key={`${citation}-${match.index}`} className="inline-citation" title={citation}>({meta.inlineLabel})</span>
        ),
      );
    } else {
      parts.push(match[0]);
    }
    lastIndex = markerPattern.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return <p className="answer-direct">{parts}</p>;
}

function citationMeta(citation: string, row?: EvidenceExtraction, chunk?: RetrievedChunk) {
  const sourceType = row?.source_type ?? chunk?.source_type;
  const title = row?.title || chunk?.title || citation;
  const url = row?.source_url || chunk?.url || null;
  const publicationDate = row?.publication_date || chunk?.publication_date || "";
  const year = publicationDate.match(/(?:19|20)\d{2}/)?.[0];
  const authors = safeList(row?.authors).filter(Boolean);
  const firstAuthor = authors[0]?.replace(/\s+[A-Z][A-Z.-]{0,7}$/i, "").trim();
  const compactTitle = title.length > 72 ? `${title.slice(0, 69).trimEnd()}…` : title;

  if (sourceType === "pubmed") {
    const authorLabel = firstAuthor ? `${firstAuthor}${authors.length > 1 ? " et al." : ""}` : "PubMed";
    return {
      url,
      inlineLabel: `${authorLabel}${year ? `, ${year}` : ""}`,
      displayLabel: firstAuthor ? `${authorLabel} (${year || "n.d."}) — ${compactTitle}` : `${compactTitle}${year ? ` (${year})` : ""}`,
    };
  }
  if (sourceType === "clinical_trials") {
    return { url, inlineLabel: `ClinicalTrials.gov${year ? `, ${year}` : ""}`, displayLabel: `${compactTitle} — ClinicalTrials.gov` };
  }
  if (sourceType === "fda_label") {
    return { url, inlineLabel: "FDA label", displayLabel: `${compactTitle} — FDA label` };
  }
  if (sourceType === "fda_adverse_event") {
    return { url, inlineLabel: "openFDA reports", displayLabel: `${compactTitle} — openFDA reports` };
  }
  return { url, inlineLabel: `source ${citation}`, displayLabel: citation };
}

function AnswerDisclosure({ title, meta, children }: { title: string; meta: string; children: ReactNode }) {
  return (
    <details className="answer-disclosure">
      <summary>
        <span>{title}</span>
        <span>{meta}</span>
        <ChevronDown aria-hidden="true" />
      </summary>
      <div className="answer-disclosure-content">{children}</div>
    </details>
  );
}

function AnswerTrace({ items }: { items: { label: string; value: string; detail: string }[] }) {
  return (
    <section className="answer-list-group" aria-labelledby="answer-trace-title">
      <h5 id="answer-trace-title">Answer trace</h5>
      <dl className="answer-trace">
        {items.map((item) => (
          <div key={`${item.label}-${item.value}`}>
            <dt>{item.label}</dt>
            <dd><strong>{item.value}</strong>{item.detail ? <span>{item.detail}</span> : null}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function AnswerList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="answer-list-group">
      <h5>{title}</h5>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </section>
  );
}

function CitationSheet({
  row,
  onOpenChange,
  onReview,
}: {
  row: EvidenceExtraction | null;
  onOpenChange: (open: boolean) => void;
  onReview: (row: EvidenceExtraction, status: EvidenceExtraction["review_status"]) => void;
}) {
  return (
    <Sheet open={Boolean(row)} onOpenChange={onOpenChange}>
      <SheetContent className="h-dvh max-h-dvh w-full overflow-hidden border-l border-ink/12 bg-paper text-ink shadow-2xl sm:!max-w-2xl">
        {row && (
          <>
            <SheetHeader className="shrink-0 gap-2 border-b border-ink/10 bg-paper/95 pr-14">
              <SheetTitle className="break-words text-xl font-semibold leading-6 text-ink">{row.citation}</SheetTitle>
              <SheetDescription className="line-clamp-3 text-sm leading-5 text-ink/62">{row.title}</SheetDescription>
              {row.source_url ? (
                <a
                  href={row.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex h-8 w-fit items-center gap-1 rounded-sm border border-ink/15 bg-ink px-3 text-sm font-semibold text-paper transition hover:bg-ink/85"
                >
                  Open original source <ExternalLink data-icon="inline-end" />
                </a>
              ) : (
                <span className="mt-3 inline-flex h-8 w-fit items-center rounded-sm border border-ink/10 px-3 text-sm font-semibold text-ink/68">
                  No source link available
                </span>
              )}
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-8">
              <div className="flex flex-col gap-4 py-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{sourceLabels[row.source_type]}</Badge>
                  <Badge variant={row.review_status === "needs_review" ? "destructive" : "outline"}>{reviewLabel(row.review_status)}</Badge>
                  <Badge variant="outline">{Math.round(row.confidence * 100)}% confidence</Badge>
                </div>
                <Separator />
                <ListField label="TrialLens source understanding" items={row.source_understanding} empty="No source-understanding profile was stored for this row." />
                <Field label="Source overview" value={row.source_overview || row.title} emphasis />
                <Field label="Study design / source context" value={row.methods_context || "Study design or source methods were not separately extracted."} />
                <ListField label="Source sections read" items={row.source_sections} empty="No source sections were stored for this row." />
                <ListField label="Key findings TrialLens read" items={row.key_findings} empty="No separate key findings were extracted beyond the source overview and quote." />
                <ListField label="Source passages TrialLens used" items={row.source_passages} empty="No source passages were stored for this row." />
                <ListField label="Evidence limits" items={row.evidence_limitations} empty="No additional source-level limitations were extracted." muted />
                <KeyValueField label="Field evidence map" items={row.field_evidence} empty="No field-level evidence map was stored for this row." />
                <Field label="Supporting quote" value={row.supporting_quote} emphasis />
                <Field label="Population / context" value={distinctFieldValue(row.population_context, row.supporting_quote, "Not separately extracted. Use the original source for exact eligibility or population criteria.")} />
                <Field label="Intervention" value={distinctFieldValue(row.intervention, row.supporting_quote, "Not separately extracted from the indexed summary.")} />
                <Field label="Comparator" value={distinctFieldValue(row.comparator, row.supporting_quote, "No comparator was separately extracted from the indexed summary.")} />
                <Field label="Outcome / result" value={distinctFieldValue(row.outcome_result, row.supporting_quote, "No separate outcome/result summary was extracted beyond the supporting quote.")} />
                <Field label="Safety note" value={distinctFieldValue(row.safety_note, row.supporting_quote, "No safety-specific note was separately extracted.")} />
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button type="button" onClick={() => onReview(row, "reviewed")}>Mark reviewed</Button>
                  <Button type="button" variant="outline" onClick={() => onReview(row, "needs_review")}>Needs review</Button>
                </div>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function ListField({ label, items, empty, muted }: { label: string; items?: string[]; empty: string; muted?: boolean }) {
  const listItems = safeList(items);
  const visibleItems = listItems.length ? listItems : [empty];
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink/68">{label}</p>
      <div className={cn("rounded-sm border p-3", muted ? "border-ink/10 bg-slide/65 text-ink/66" : "border-moss/18 bg-fog/35 text-ink/78")}>
        <ul className="flex list-disc flex-col gap-2 pl-4 text-sm leading-6">
          {visibleItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function KeyValueField({ label, items, empty }: { label: string; items?: Record<string, string>; empty: string }) {
  const entries = Object.entries(items ?? {}).filter(([, value]) => value.trim().length > 0);
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink/68">{label}</p>
      <div className="rounded-sm border border-moss/18 bg-fog/35 p-3 text-ink/78">
        {entries.length ? (
          <dl className="flex flex-col gap-3 text-sm leading-6">
            {entries.map(([key, value]) => (
              <div key={key} className="grid gap-1">
                <dt className="font-semibold text-ink">{key}</dt>
                <dd className="text-ink/70">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm leading-6 text-ink/62">{empty}</p>
        )}
      </div>
    </div>
  );
}

function safeList<T>(items: T[] | null | undefined): T[] {
  return Array.isArray(items) ? items : [];
}

function extractionRowsNeedRefresh(rows: EvidenceExtraction[]) {
  return rows.some((row) => {
    return (
      safeList(row.source_sections).length === 0 ||
      safeList(row.source_understanding).length === 0 ||
      safeList(row.source_passages).length === 0 ||
      Object.keys(row.field_evidence ?? {}).length === 0
    );
  });
}

function Field({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink/68">{label}</p>
      <p className={cn("rounded-sm border p-3 text-sm leading-6", emphasis ? "border-moss/25 bg-fog/35 text-ink/82" : "border-ink/10 bg-slide/65 text-ink/72")}>
        {value}
      </p>
    </div>
  );
}

function reviewLabel(status: EvidenceExtraction["review_status"]) {
  if (status === "reviewed") return "Checked";
  if (status === "needs_review") return "Low confidence";
  return "Not checked";
}

function compactSafetyNote(row: EvidenceExtraction) {
  const note = fieldValue(row.safety_note, row.supporting_quote, "");
  return note || null;
}

function fieldValue(value: string, supportingQuote: string, fallback: string) {
  const cleanValue = value.trim();
  const cleanQuote = supportingQuote.trim();
  if (!cleanValue) return fallback;
  if (cleanQuote && cleanValue === cleanQuote) return fallback;
  return cleanValue;
}

function distinctFieldValue(value: string, supportingQuote: string, fallback: string) {
  const cleanValue = value.trim();
  const cleanQuote = supportingQuote.trim();
  if (!cleanValue) return fallback;
  if (cleanQuote && cleanValue === cleanQuote) return fallback;
  if (cleanQuote && cleanQuote.includes(cleanValue) && cleanValue.length > 120) return fallback;
  return cleanValue;
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </div>
  );
}

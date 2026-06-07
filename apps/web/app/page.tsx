"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle2,
  FileSearch,
  FlaskConical,
  Loader2,
  MessageSquareText,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Answer, Brief, EvidenceSource, EvalReport, Workspace, api } from "@/lib/api";

const sourceLabels: Record<string, string> = {
  pubmed: "PubMed",
  clinical_trials: "ClinicalTrials.gov",
  fda_label: "FDA labels",
  fda_adverse_event: "FDA adverse reports",
};

const navItems = [
  { label: "Workspace", href: "#workspace" },
  { label: "Ask", href: "#ask" },
  { label: "Sources", href: "#sources" },
];

export default function Home() {
  const [condition, setCondition] = useState("type 2 diabetes");
  const [intervention, setIntervention] = useState("metformin");
  const [question, setQuestion] = useState("What does the evidence say about benefits and safety limitations?");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [sources, setSources] = useState<EvidenceSource[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [evals, setEvals] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAllRetrieved, setShowAllRetrieved] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);

  const counts = useMemo(() => {
    return sources.reduce<Record<string, number>>((acc, source) => {
      acc[source.source_type] = (acc[source.source_type] ?? 0) + 1;
      return acc;
    }, {});
  }, [sources]);

  const totalSources = sources.length;
  const isReady = Boolean(workspace && totalSources > 0);
  const visibleRetrieved = showAllRetrieved ? answer?.retrieved_chunks ?? [] : answer?.retrieved_chunks.slice(0, 3) ?? [];
  const hiddenRetrievedCount = Math.max((answer?.retrieved_chunks.length ?? 0) - visibleRetrieved.length, 0);
  const visibleSources = showAllSources ? sources : sources.slice(0, 6);
  const hiddenSourceCount = Math.max(sources.length - visibleSources.length, 0);

  async function buildWorkspace(event?: FormEvent) {
    event?.preventDefault();
    if (busy || condition.trim().length < 2) return;
    setError(null);
    setAnswer(null);
    setBrief(null);
    setEvals(null);
    setSources([]);
    setShowAllRetrieved(false);
    setShowAllSources(false);
    setBusy("Creating workspace");
    try {
      const created = await api.createWorkspace(condition.trim(), intervention.trim());
      setWorkspace(created);
      setBusy("Indexing public evidence");
      await api.ingest(created.id);
      const [indexed, generatedBrief, report] = await Promise.all([
        api.sources(created.id),
        api.brief(created.id),
        api.evals(),
      ]);
      setSources(indexed);
      setBrief(generatedBrief);
      setEvals(report);
      document.querySelector("#workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong while building the workspace.");
    } finally {
      setBusy(null);
    }
  }

  async function ask() {
    if (!workspace || busy || question.trim().length < 3) return;
    setError(null);
    setBusy("Retrieving cited passages");
    try {
      const response = await api.ask(workspace.id, question.trim());
      setAnswer(response);
      setShowAllRetrieved(false);
      document.querySelector("#answer")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Question failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="son-flow film-grain min-h-screen overflow-hidden">
      <nav className="fixed left-0 right-0 top-4 z-40 mx-auto flex max-w-7xl items-center justify-between px-4">
        <a href="#home" className="flex items-center gap-2 text-paper drop-shadow">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-paper text-ink">
            <FileSearch size={17} />
          </span>
          <span className="font-semibold">TrialLens</span>
        </a>
        <div className="hidden rounded-full border border-paper/35 bg-paper/12 px-2 py-2 text-sm text-paper shadow-xl backdrop-blur-xl md:flex">
          {navItems.map((item) => (
            <a key={item.href} className="nav-link rounded-full px-4 py-1.5" href={item.href}>
              {item.label}
            </a>
          ))}
        </div>
      </nav>

      <section id="home" className="relative min-h-screen bg-black">
        <div className="hero-landscape valley-current relative grid min-h-screen overflow-hidden shadow-2xl">
          <div className="flow-ribbon ribbon-one" aria-hidden="true" />
          <div className="flow-ribbon ribbon-two" aria-hidden="true" />
          <div className="flow-ribbon ribbon-three" aria-hidden="true" />
          <div className="drift-figures" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="mycelium-cloud left-cloud" aria-hidden="true" />
          <div className="mycelium-cloud right-cloud" aria-hidden="true" />

          <div className="relative z-10 mx-auto grid w-full max-w-7xl content-end gap-8 px-5 pb-8 pt-28 text-paper lg:grid-cols-[1fr_430px] lg:items-end lg:pb-14">
            <div>
              <p className="poem-line mb-6 max-w-sm font-display text-3xl leading-none text-paper/72">
                I am a valley of evidence
                <span className="block pl-20 text-paper/45">see you in the sources</span>
              </p>
              <h1 className="font-display text-[19vw] font-semibold leading-[0.72] tracking-[-0.09em] drop-shadow-2xl sm:text-[14vw] lg:text-[10.8rem]">
                TrialLens
              </h1>
              <p className="mt-6 max-w-3xl text-balance text-lg leading-7 text-paper/88 md:text-2xl">
                Explore biomedical literature, trials, and FDA records through a calmer evidence workspace with citations you can inspect.
              </p>
            </div>

            <form onSubmit={buildWorkspace} className="hero-search shadow-2xl shadow-black/35">
              <div className="mb-5 flex items-center justify-between border-b border-ink/15 pb-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-ink/45">Start a workspace</p>
                  <h2 className="font-display text-4xl font-semibold tracking-[-0.05em] text-ink">Ask from evidence.</h2>
                </div>
                <Sparkles className="text-moss" size={21} />
              </div>
              <label className="mb-3 block">
                <span className="mb-1 block text-[10px] font-bold uppercase tracking-[0.22em] text-ink/55">Condition</span>
                <input
                  value={condition}
                  onChange={(event) => setCondition(event.target.value)}
                  className="w-full rounded-none border border-ink/20 bg-paper/85 px-3 py-3 text-ink outline-none transition focus:border-moss"
                  placeholder="e.g. type 2 diabetes"
                />
              </label>
              <label className="mb-5 block">
                <span className="mb-1 block text-[10px] font-bold uppercase tracking-[0.22em] text-ink/55">Drug or intervention</span>
                <input
                  value={intervention}
                  onChange={(event) => setIntervention(event.target.value)}
                  className="w-full rounded-none border border-ink/20 bg-paper/85 px-3 py-3 text-ink outline-none transition focus:border-moss"
                  placeholder="e.g. metformin"
                />
              </label>
              <button
                type="submit"
                disabled={Boolean(busy)}
                className="group flex w-full items-center justify-between rounded-full bg-ink px-5 py-3 font-semibold text-paper transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="flex items-center gap-2">
                  {busy ? <Loader2 className="animate-spin" size={18} /> : <Brain size={18} />}
                  {busy ?? "Build workspace"}
                </span>
                <ArrowRight className="transition group-hover:translate-x-1" size={18} />
              </button>
              {error && <p className="mt-4 border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
            </form>
          </div>
        </div>
      </section>

      <section className="transition-band relative px-5 py-16 text-paper">
        <div className="contour-field" aria-hidden="true" />
        <div className="mx-auto grid max-w-7xl gap-6 md:grid-cols-[0.8fr_1.2fr] md:items-end">
          <p className="font-display text-5xl leading-none tracking-[-0.05em] text-paper/80">
            From landscape
            <span className="block pl-14 text-paper/42">to literature.</span>
          </p>
          <p className="max-w-2xl text-balance text-lg leading-7 text-paper/68">
            The workspace keeps the atmosphere of the landing page, but turns the scenery into a practical evidence trail: sources, passages, citations, and uncertainty.
          </p>
        </div>
      </section>

      <section id="workspace" className="workspace-section relative mx-auto max-w-7xl px-5 py-14">
        <div className="bio-bloom pointer-events-none absolute -left-20 top-20 h-80 w-80 rounded-full opacity-70" />
        <div className="mb-8 grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
          <div className="paper-panel relative z-10 rounded-sm p-6">
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-ink/45">Workspace</p>
            <h2 className="mt-3 font-display text-6xl font-semibold leading-none tracking-[-0.06em]">A readable map of the evidence.</h2>
            <p className="mt-5 max-w-2xl text-lg leading-7 text-ink/68">
              TrialLens keeps the generated answer secondary to the evidence trail: source type, citation, retrieved passage, and limitation.
            </p>
          </div>
          <div className="dark-panel relative z-10 rounded-sm p-6 text-paper">
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-paper/45">Current topic</p>
            <p className="mt-4 font-display text-5xl font-semibold leading-none tracking-[-0.05em]">
              {condition || "Condition"}
              {intervention ? <span className="block text-paper/55">+ {intervention}</span> : null}
            </p>
            <div className="mt-6 flex items-center gap-2 text-sm text-paper/70">
              <ShieldAlert size={16} /> Evidence navigation only. Not clinical guidance.
            </div>
          </div>
        </div>

        <div className="relative z-10 grid gap-4 md:grid-cols-4">
          {Object.entries(sourceLabels).map(([key, label]) => (
            <a key={key} href="#sources" className="metric-card rounded-sm p-4 transition hover:-translate-y-1 hover:shadow-2xl">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink/50">{label}</p>
              <p className="mt-4 font-display text-6xl font-semibold tracking-[-0.06em]">{counts[key] ?? 0}</p>
            </a>
          ))}
        </div>
      </section>

      <section id="ask" className="mx-auto max-w-7xl px-5 pb-10">
        <div className="dark-panel rounded-sm p-5 text-paper md:p-7">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-paper/45">Ask</p>
              <h2 className="font-display text-5xl font-semibold tracking-[-0.05em]">Question the indexed sources.</h2>
            </div>
            <button
              onClick={ask}
              disabled={!isReady || Boolean(busy)}
              className="flex items-center gap-2 rounded-full bg-paper px-5 py-2 font-semibold text-ink transition hover:bg-fog disabled:cursor-not-allowed disabled:opacity-50"
            >
              <MessageSquareText size={17} /> Ask evidence
            </button>
          </div>
          {!isReady && (
            <p className="mb-4 border border-paper/15 bg-paper/8 p-3 text-sm text-paper/68">
              Build a workspace first. Once sources are indexed, this panel becomes a cited Q&A interface.
            </p>
          )}
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="min-h-28 w-full rounded-none border border-paper/20 bg-paper p-3 text-ink shadow-inner shadow-black/20 outline-none placeholder:text-ink/45 focus:border-fog"
          />
          {answer && (
            <div id="answer" className="mt-6 grid gap-4 lg:grid-cols-[1fr_380px]">
              <div className="border border-paper/15 bg-paper/5 p-5">
                <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-paper/60">Short answer</p>
                <p className="text-lg leading-7">{answer.short_answer}</p>
                <div className="mt-5 space-y-3">
                  {answer.evidence.map((item) => (
                    <p key={item} className="bg-paper/10 p-3 text-sm leading-6">
                      {item}
                    </p>
                  ))}
                </div>
                <div className="mt-5 border-t border-paper/20 pt-4">
                  <p className="mb-2 font-semibold">Limitations</p>
                  {answer.limitations.map((item) => (
                    <p key={item} className="text-sm text-paper/75">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-xs leading-5 text-paper/55">
                  Match shows how strongly each retrieved passage aligned with your question. It is a retrieval relevance signal, not medical certainty.
                </p>
                {visibleRetrieved.map((chunk) => (
                  <div key={chunk.chunk_id} className="border border-paper/15 bg-paper/8 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-[0.16em]">{sourceLabels[chunk.source_type]}</span>
                      <span className="rounded-full bg-paper px-2 py-1 text-xs font-semibold text-ink">
                        {Math.round(chunk.score * 100)}% match
                      </span>
                    </div>
                    <p className="mb-2 font-semibold">{chunk.citation}</p>
                    <p className="text-sm leading-6 text-paper/72">{chunk.text}</p>
                  </div>
                ))}
                {hiddenRetrievedCount > 0 || showAllRetrieved ? (
                  <button
                    type="button"
                    onClick={() => setShowAllRetrieved((value) => !value)}
                    className="w-full rounded-full border border-paper/20 px-4 py-2 text-sm font-semibold text-paper/82 transition hover:border-paper/60 hover:bg-paper/10"
                  >
                    {showAllRetrieved ? "Show fewer passages" : `See ${hiddenRetrievedCount} more passages`}
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </div>
      </section>

      <section id="sources" className="lower-evidence-section relative mx-auto grid max-w-7xl gap-6 px-5 pb-16 xl:grid-cols-[1fr_420px]">
        <div className="lower-contours" aria-hidden="true" />
        <div className="paper-panel rounded-sm p-5 md:p-7">
          <div className="mb-5 flex items-center gap-3">
            <BookOpen className="text-moss" />
            <h2 className="font-display text-5xl font-semibold tracking-[-0.05em]">Source explorer</h2>
          </div>
          <div className="space-y-3">
            {sources.length === 0 && <p className="text-ink/65">Build a workspace to inspect normalized biomedical sources.</p>}
            {visibleSources.map((source) => (
              <article key={source.id} className="source-card p-4 transition hover:-translate-y-0.5">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-moss/10 px-2 py-1 text-xs font-bold uppercase tracking-[0.14em] text-moss">
                    {sourceLabels[source.source_type]}
                  </span>
                  {source.phase && <span className="text-xs font-semibold text-ink/60">{source.phase}</span>}
                  {source.status && <span className="text-xs font-semibold text-ink/60">{source.status}</span>}
                </div>
                <h3 className="font-semibold">{source.title}</h3>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-ink/70">{source.abstract}</p>
              </article>
            ))}
            {hiddenSourceCount > 0 || showAllSources ? (
              <button
                type="button"
                onClick={() => setShowAllSources((value) => !value)}
                className="w-full rounded-full border border-moss/25 bg-paper/60 px-4 py-2 text-sm font-semibold text-ink transition hover:border-moss/60 hover:bg-paper"
              >
                {showAllSources ? "Show fewer sources" : `See all sources (${hiddenSourceCount} more)`}
              </button>
            ) : null}
          </div>
        </div>

        <div id="brief" className="space-y-6">
          <div className="paper-panel rounded-sm p-5 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <FlaskConical className="text-clinical" />
              <h2 className="font-display text-5xl font-semibold tracking-[-0.05em]">Evidence brief</h2>
            </div>
            {brief ? (
              <div className="space-y-3 text-sm leading-6">
                <p className="font-semibold">{brief.overview}</p>
                {brief.key_claims.slice(0, 3).map((claim) => (
                  <p key={claim} className="bg-paper/70 p-3">
                    {claim}
                  </p>
                ))}
                <p className="font-semibold text-signal">{brief.safety_note}</p>
              </div>
            ) : (
              <p className="text-ink/65">A generated brief appears after ingestion.</p>
            )}
          </div>

          <div id="evals" className="paper-panel rounded-sm p-5 md:p-7">
            <div className="mb-5 flex items-center gap-3">
              <Activity className="text-moss" />
              <h2 className="font-display text-5xl font-semibold tracking-[-0.05em]">Evaluation lab</h2>
            </div>
            {evals ? (
              <div className="space-y-3">
                {evals.metrics.map((metric) => (
                  <div key={metric.name} className="bg-paper/70 p-3">
                    <div className="mb-1 flex items-center justify-between gap-4">
                      <span className="font-semibold">{metric.name.replaceAll("_", " ")}</span>
                      <span className="font-display text-3xl font-semibold">{Math.round(metric.score * 100)}%</span>
                    </div>
                    <p className="text-xs leading-5 text-ink/65">{metric.description}</p>
                  </div>
                ))}
                <div className="flex items-center gap-2 text-sm font-semibold text-moss">
                  <CheckCircle2 size={16} /> Citation-grounded MVP checks active
                </div>
              </div>
            ) : (
              <p className="text-ink/65">Evaluation results appear after workspace creation.</p>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

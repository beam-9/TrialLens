"use client";

import { useMemo, useState } from "react";
import { Activity, ArrowUpRight, BookOpen, Brain, CheckCircle2, FileSearch, FlaskConical, Loader2, ShieldAlert } from "lucide-react";
import { Answer, Brief, EvidenceSource, EvalReport, Workspace, api } from "@/lib/api";

const sourceLabels: Record<string, string> = {
  pubmed: "PubMed",
  clinical_trials: "ClinicalTrials.gov",
  fda_label: "FDA labels",
  fda_adverse_event: "FDA adverse reports",
};

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

  const counts = useMemo(() => {
    return sources.reduce<Record<string, number>>((acc, source) => {
      acc[source.source_type] = (acc[source.source_type] ?? 0) + 1;
      return acc;
    }, {});
  }, [sources]);

  async function runWorkspace() {
    setError(null);
    setBusy("Creating workspace");
    try {
      const created = await api.createWorkspace(condition, intervention);
      setWorkspace(created);
      setBusy("Ingesting evidence");
      await api.ingest(created.id);
      const indexed = await api.sources(created.id);
      setSources(indexed);
      const generatedBrief = await api.brief(created.id);
      const report = await api.evals();
      setBrief(generatedBrief);
      setEvals(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(null);
    }
  }

  async function ask() {
    if (!workspace) return;
    setError(null);
    setBusy("Retrieving evidence");
    try {
      setAnswer(await api.ask(workspace.id, question));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Question failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="film-grain min-h-screen overflow-hidden">
      <nav className="pointer-events-none fixed left-0 right-0 top-5 z-40 mx-auto flex max-w-6xl items-center justify-between px-5">
        <div className="pointer-events-auto flex items-center gap-2 text-paper drop-shadow">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-paper text-ink">
            <FileSearch size={16} />
          </span>
          <span className="font-semibold">TrialLens.ai</span>
        </div>
        <div className="pointer-events-auto hidden rounded-full border border-paper/35 bg-paper/12 px-3 py-2 text-sm text-paper shadow-xl backdrop-blur-xl md:flex">
          <a className="px-5" href="#workspace">Workspace</a>
          <a className="px-5" href="#sources">Sources</a>
          <a className="px-5" href="#evals">Evals</a>
        </div>
        <a
          href="#workspace"
          className="pointer-events-auto rounded-full bg-paper px-5 py-2 text-sm font-semibold text-ink shadow-xl shadow-black/20"
        >
          Start
        </a>
      </nav>

      <section className="relative min-h-[92vh] bg-black p-3 sm:p-6">
        <div className="hero-landscape relative flex min-h-[calc(92vh-3rem)] items-end overflow-hidden rounded-sm border border-paper/20 shadow-2xl">
          <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center px-5 pb-10 text-center text-paper sm:pb-16">
            <h1 className="font-display text-[18vw] font-semibold leading-[0.74] tracking-[-0.08em] drop-shadow-2xl sm:text-[13vw] lg:text-[10.5rem]">
              TrialLens
            </h1>
            <p className="mt-6 max-w-3xl text-balance text-lg leading-6 text-paper/86 md:text-xl">
              A biomedical evidence workspace that retrieves public literature, trials, and FDA records, then answers with inspectable citations.
            </p>
            <div className="mt-8 flex w-full max-w-2xl items-center rounded-full border border-paper/40 bg-paper/16 p-1 shadow-2xl backdrop-blur-xl">
              <span className="flex-1 truncate px-5 text-left text-sm text-paper/85">
                {condition} {intervention ? `+ ${intervention}` : ""}
              </span>
              <a href="#workspace" className="rounded-full bg-paper px-5 py-3 text-sm font-bold text-ink">
                Build workspace
              </a>
            </div>
          </div>
        </div>
      </section>

      <section id="workspace" className="relative mx-auto grid max-w-7xl gap-6 px-5 py-10 lg:grid-cols-[420px_1fr]">
        <div className="bio-bloom pointer-events-none absolute -left-20 top-24 h-80 w-80 rounded-full opacity-70" />
        <aside className="relative z-10 h-fit rounded-sm bg-slide p-5 shadow-2xl shadow-ink/20 ring-1 ring-ink/10 lg:sticky lg:top-5">
          <div className="mb-8 flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-ink/45">Research console</p>
              <h2 className="mt-3 font-display text-5xl font-semibold leading-none tracking-[-0.04em]">Ask the evidence.</h2>
            </div>
            <div className="grid h-10 w-10 place-items-center rounded-full border border-ink/25">
              <ArrowUpRight size={18} />
            </div>
          </div>

          <div className="mb-6 border-y border-ink/20 py-4 text-sm leading-6 text-ink/72">
            <div className="mb-1 flex items-center gap-2 font-semibold text-ink">
              <ShieldAlert size={16} /> Navigation, not advice
            </div>
            Citations are mandatory. Patient-specific treatment guidance is outside scope.
          </div>

          <label className="mb-3 block">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-[0.22em] text-ink/55">Condition</span>
            <input
              value={condition}
              onChange={(event) => setCondition(event.target.value)}
              className="w-full rounded-none border border-ink/25 bg-paper px-3 py-3 outline-none focus:border-moss"
            />
          </label>
          <label className="mb-5 block">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-[0.22em] text-ink/55">Drug or intervention</span>
            <input
              value={intervention}
              onChange={(event) => setIntervention(event.target.value)}
              className="w-full rounded-none border border-ink/25 bg-paper px-3 py-3 outline-none focus:border-moss"
            />
          </label>

          <button
            onClick={runWorkspace}
            disabled={Boolean(busy)}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-ink px-4 py-3 font-semibold text-paper transition hover:bg-moss disabled:opacity-60"
          >
            {busy ? <Loader2 className="animate-spin" size={18} /> : <Brain size={18} />}
            {busy ?? "Ingest public evidence"}
          </button>

          {workspace && (
            <div className="mt-5 border border-ink/15 bg-paper p-3 text-sm">
              <p className="font-semibold">Workspace ready</p>
              <p className="break-all text-ink/60">{workspace.id}</p>
            </div>
          )}
          {error && <p className="mt-4 bg-red-100 p-3 text-sm text-red-800">{error}</p>}
        </aside>

        <section className="relative z-10 space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            {Object.entries(sourceLabels).map(([key, label]) => (
              <div key={key} className="rounded-sm bg-slide p-4 shadow-xl shadow-ink/10 ring-1 ring-ink/10">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink/50">{label}</p>
                <p className="mt-4 font-display text-6xl font-semibold tracking-[-0.06em]">{counts[key] ?? 0}</p>
              </div>
            ))}
          </div>

          <div className="rounded-sm bg-[#20211f] p-5 text-paper shadow-2xl shadow-ink/25">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-paper/45">Ask Evidence</p>
                <h2 className="font-display text-5xl font-semibold tracking-[-0.04em]">Cited question answering</h2>
              </div>
              <button
                onClick={ask}
                disabled={!workspace || Boolean(busy)}
                className="rounded-full bg-paper px-5 py-2 font-semibold text-ink disabled:opacity-50"
              >
                Ask
              </button>
            </div>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              className="min-h-24 w-full rounded-none border border-paper/20 bg-paper/8 p-3 text-paper outline-none placeholder:text-paper/40 focus:border-paper/60"
            />
            {answer && (
              <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_360px]">
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
                  {answer.retrieved_chunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="border border-paper/15 bg-paper/8 p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-[0.16em]">{sourceLabels[chunk.source_type]}</span>
                        <span className="rounded-full bg-paper px-2 py-1 text-xs font-semibold text-ink">
                          {chunk.score}
                        </span>
                      </div>
                      <p className="mb-2 font-semibold">{chunk.citation}</p>
                      <p className="text-sm leading-6 text-paper/72">{chunk.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
            <section id="sources" className="rounded-sm bg-slide p-5 shadow-xl shadow-ink/10 ring-1 ring-ink/10">
              <div className="mb-4 flex items-center gap-3">
                <BookOpen className="text-moss" />
                <h2 className="font-display text-4xl font-semibold tracking-[-0.04em]">Source explorer</h2>
              </div>
              <div className="space-y-3">
                {sources.length === 0 && <p className="text-ink/65">Build a workspace to inspect normalized biomedical sources.</p>}
                {sources.map((source) => (
                  <article key={source.id} className="source-card p-4">
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
              </div>
            </section>

            <section className="space-y-6">
              <div className="rounded-sm bg-slide p-5 shadow-xl shadow-ink/10 ring-1 ring-ink/10">
                <div className="mb-4 flex items-center gap-3">
                  <FlaskConical className="text-clinical" />
                  <h2 className="font-display text-4xl font-semibold tracking-[-0.04em]">Evidence brief</h2>
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

              <div id="evals" className="rounded-sm bg-slide p-5 shadow-xl shadow-ink/10 ring-1 ring-ink/10">
                <div className="mb-4 flex items-center gap-3">
                  <Activity className="text-moss" />
                  <h2 className="font-display text-4xl font-semibold tracking-[-0.04em]">Evaluation lab</h2>
                </div>
                {evals ? (
                  <div className="space-y-3">
                    {evals.metrics.map((metric) => (
                      <div key={metric.name} className="bg-paper/70 p-3">
                        <div className="mb-1 flex items-center justify-between">
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
            </section>
          </div>
        </section>
      </section>
    </main>
  );
}

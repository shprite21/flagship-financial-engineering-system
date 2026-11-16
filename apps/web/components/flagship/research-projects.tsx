'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Field, Panel, Pnl, Status } from './research-primitives';
import ProjectSpecification from './project-specification';
import ProjectComparison from './project-comparison';
import { PerformancePlot } from './performance-plot';
import { researchApi, type Catalog } from '@/lib/flagship/research';
import { initialProject, projectApi, type Comparison, type Project, type ProjectSpec } from '@/lib/flagship/projects';

const stages = ['THESIS', 'DATA', 'SIGNAL', 'EXPERIMENTS', 'COMPARE', 'VALIDATION', 'ROBUSTNESS', 'OOS', 'FREEZE', 'FORWARD', 'MONITOR', 'PAPER'] as const;
type Stage = typeof stages[number];
const json = (value: unknown) => JSON.stringify(value, null, 2);
function Detail({ label, value }: { label: string; value: unknown }) { return <details className="rounded border p-3"><summary className="cursor-pointer text-sm">{label}</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{json(value)}</pre></details>; }
function SensitivitySurface({ value }: { value: unknown }) {
  if (!Array.isArray(value)) return null;
  const rows = value as { candidate_id: string; lookbacks?: Record<string, number>; total_return?: number; sharpe?: number; max_drawdown?: number; reason?: string }[];
  return <div className="my-3 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="pb-2 text-left text-xs text-muted-foreground">Complete local lookback surface; no optimum selected</caption><thead><tr>{['Lookbacks', 'Net return', 'Sharpe', 'Drawdown', 'Failure'].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{rows.map(r => <tr key={r.candidate_id} className="border-t"><td className="p-2">{r.lookbacks ? Object.values(r.lookbacks).join(', ') : 'N/A'}</td><td className="p-2"><Pnl value={r.total_return} /></td><td className="p-2">{numeric(r.sharpe)}</td><td className="p-2"><Pnl value={r.max_drawdown} /></td><td className="p-2">{r.reason ?? '—'}</td></tr>)}</tbody></table></div>;
}
const numeric = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? 'N/A' : value.toFixed(3);

export default function ResearchProjects() {
  const [book, setBook] = useState<{ id: string; title: string }[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [draft, setDraft] = useState<ProjectSpec>(initialProject);
  const [stage, setStage] = useState<Stage>('THESIS');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('Prespecified investigation of the economic hypothesis and its failure conditions.');
  const [dataset, setDataset] = useState('');
  const [trialId, setTrialId] = useState('');
  const [version, setVersion] = useState('');
  const [lookbacks, setLookbacks] = useState('');
  const [comparisonSnapshot, setComparisonSnapshot] = useState<{ projectId: string; version: string; value: Comparison } | null>(null);
  const activeProject = useRef<string | null>(null);
  const refreshEpoch = useRef(0);
  const editingRefresh = useRef(false);
  const [expected, setExpected] = useState('{}');
  const [expectationBasis, setExpectationBasis] = useState('Researcher expectations are specified before prospective observation; historical estimates are uncertain.');
  const [killDrawdown, setKillDrawdown] = useState(.15);
  const [killGross, setKillGross] = useState(1);
  const [killStale, setKillStale] = useState(7);
  const [forwardMode, setForwardMode] = useState('manual');
  const [provider, setProvider] = useState('unconfigured');
  const [reference, setReference] = useState({ citation: '', authors: '', url: '', finding: '', relevance: '', assumptions: '', doi: '' });
  const [eventKind, setEventKind] = useState('signal');
  const [observedAt, setObservedAt] = useState('');
  const [eventWeights, setEventWeights] = useState('{}');
  const [eventNav, setEventNav] = useState(1000000);
  const [eventCost, setEventCost] = useState(0);
  const [signalId, setSignalId] = useState('');
  const [protocolText, setProtocolText] = useState('{}');
  const trial = project?.trials.find(t => t.id === trialId);
  const validation = [...(project?.validations ?? [])].reverse().find(v => v.trial_id === trialId);
  const frozen = project?.freezes.find(f => f.id === version);
  const projectId = project?.id;
  const comparison = comparisonSnapshot?.projectId === projectId && comparisonSnapshot?.version === version ? comparisonSnapshot.value : null;
  const running = project?.tasks.some(t => t.status === 'queued' || t.status === 'running') || project?.trials.some(t => ['queued', 'running', 'launched'].includes(t.status)) || project?.validations.some(v => ['queued', 'running'].includes(v.status));

  const refresh = useCallback(async (id: string, edit = false) => {
    if (edit) activeProject.current = id;
    if (activeProject.current !== id || (!edit && editingRefresh.current)) return;
    if (edit) editingRefresh.current = true;
    const ticket = ++refreshEpoch.current;
    let next: Project;
    try { next = await projectApi<Project>('/' + id); }
    catch (cause) { if (activeProject.current === id && ticket === refreshEpoch.current) throw cause; return; }
    finally { if (ticket === refreshEpoch.current) editingRefresh.current = false; }
    if (activeProject.current !== id || ticket !== refreshEpoch.current) return;
    setProject(next);
    if (edit) { setDraft(next.spec); setProtocolText(json(next.spec.validation)); }
    setDataset(current => next.datasets.some(d => d.id === current) ? current : next.datasets[0]?.id ?? '');
    setTrialId(current => next.trials.some(t => t.id === current) ? current : next.trials.find(t => t.status === 'completed')?.id ?? next.trials[0]?.id ?? '');
    setVersion(current => next.freezes.some(v => v.id === current) ? current : next.freezes[0]?.id ?? '');
  }, []);
  const reloadBook = useCallback(async () => setBook((await projectApi<{ projects: { id: string; title: string }[] }>()).projects), []);
  useEffect(() => {
    let active = true;
    Promise.all([projectApi<{ projects: { id: string; title: string }[] }>(), researchApi<Catalog>('/catalog')])
      .then(([index, strategies]) => { if (active) { setBook(index.projects); setCatalog(strategies); } })
      .catch(cause => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!projectId || !running) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await refresh(projectId); } catch (cause) { if (active) setError((cause as Error).message); }
      if (active) timer = setTimeout(poll, 1800);
    };
    timer = setTimeout(poll, 1800);
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, running, refresh]);
  useEffect(() => {
    if (!projectId || !version || !['FORWARD', 'MONITOR', 'PAPER'].includes(stage)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await projectApi<Comparison>(`/${projectId}/versions/${version}/comparison`);
        if (active) setComparisonSnapshot({ projectId, version, value });
      } catch (cause) {
        if (active) { setComparisonSnapshot(null); setError((cause as Error).message); }
      }
      if (active) timer = setTimeout(poll, 5000);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, project, version, stage]);

  async function perform(action: () => Promise<unknown>, reload = true) {
    setBusy(true); setError('');
    try { await action(); if (project && reload) await refresh(project.id); await reloadBook(); }
    catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  const post = (path: string, body: unknown = {}) => perform(() => projectApi(`/${project!.id}${path}`, body));
  async function save(nextDraft = draft) {
    setBusy(true); setError('');
    try {
      const next = project ? await projectApi<Project>(`/${project.id}/revisions`, { parent_revision: project.revision_id, spec: nextDraft, reason }) : await projectApi<Project>('', { spec: nextDraft });
      await refresh(next.id, true); await reloadBook();
    } catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  }
  const dirty = !!project && json(draft) !== json(project.spec);
  const selectedData = project?.datasets.find(d => d.id === (trial?.dataset_id ?? dataset));
  const selectedForward = comparison?.forward.find(f => f.mode === 'manual');
  const selectionEvidence = validation?.result?.layers.find(l => l.id === 10);
  const layers = validation?.result?.layers.filter(l => stage === 'ROBUSTNESS' ? [4, 5, 6, 11, 13, 14, 16].includes(l.id) : true) ?? [];
  const candidateFreeze = project?.freezes.find(f => f.trial_id === trialId);
  const nextStage: Stage = !dataset ? 'DATA' : !trial || trial.status !== 'completed' ? 'EXPERIMENTS'
    : !validation?.result?.summary.research_gates_satisfied ? 'VALIDATION' : !project?.oos.some(o => o.trial_id === trialId) ? 'OOS'
    : !candidateFreeze ? 'FREEZE' : !project.forward.some(f => f.strategy_version_id === candidateFreeze.id) ? 'FORWARD' : 'MONITOR';

  return <section className="mx-auto grid w-full min-w-0 max-w-[1500px] gap-5 p-5 [&>*]:min-w-0" aria-label="Single-strategy research projects">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Research projects</h1><p className="mt-1 text-sm text-muted-foreground">One hypothesis, complete lineage, separate prospective evidence.</p></div><div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={() => { activeProject.current = null; refreshEpoch.current++; setProject(null); setDraft(initialProject()); setProtocolText('{}'); setDataset(''); setTrialId(''); setVersion(''); setComparisonSnapshot(null); setError(''); setStage('THESIS'); }}>New project</Button>{project && <Button variant="outline" disabled={busy} onClick={() => void perform(() => refresh(project.id))}>Refresh project</Button>}</div></div>
    <Field label="Open research project"><select aria-label="Open research project" disabled={busy} className="rounded border bg-background p-3" value={project?.id ?? ''} onChange={e => { if (e.target.value) void perform(() => refresh(e.target.value, true), false); }}><option value="">Choose a project…</option>{book.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
    <Panel title="Idea to evidence" detail="Hypothesis → data → signal and portfolio → backtest → compare → validate → freeze → prospective monitoring."><div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-3xl text-sm text-muted-foreground">{project ? 'Review the selected candidate against your saved criteria. Retain negative results and inspect robustness before revealing the final segment. A frozen version is a research record, not trading approval.' : 'Start with a falsifiable question below, or open an existing investigation. The initial configuration uses explicitly synthetic data for an offline demonstration.'}</p>{project && <Button variant="outline" onClick={() => { if (candidateFreeze) setVersion(candidateFreeze.id); setStage(nextStage); }}>Continue to {nextStage.toLowerCase()}</Button>}</div></Panel>
    {error && <div role="alert" className="rounded border border-red-400/40 p-4 text-sm text-red-200">{error}</div>}
    {project && <div className="grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-3">{[['Hypothesis revision', project.revision_id.slice(0, 12)], ['Trials retained', project.integrity.trial_count], ['Failed attempts', project.integrity.failed_trials], ['OOS reveals', project.integrity.oos_reveals], ['Frozen versions', project.freezes.length]].map(([label, value]) => <div key={String(label)} className="rounded border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 break-all font-mono">{value}</p></div>)}</div>}
    {project && <Panel title="Research integrity" detail="Counts describe evidence coverage. They are not a score or investment approval."><p className="text-sm">{project.spec.thesis.research_question}</p><p className="mt-2 text-sm text-muted-foreground">{project.spec.thesis.mechanism}</p><div className="mt-3 flex flex-wrap gap-2"><Status value={project.integrity.oos_reveals ? 'OOS revealed' : 'Final segment reserved after capture'} /><Status value={`${project.integrity.post_oos_revisions} post-OOS revisions`} /><Status value={['demo', 'synthetic'].includes(project.spec.research.data_mode) ? 'SYNTHETIC demonstration' : 'Observed historical research'} /><Status value="True unseen historical OOS: UNKNOWN" /></div><details className="mt-3 text-sm"><summary>Integrity boundaries</summary><pre className="mt-2 whitespace-pre-wrap">{json(project.integrity)}</pre></details></Panel>}
    {project && <Panel title="Candidate evidence overview" detail="Interpret performance together with integrity, search history and missing evidence."><div className="grid gap-3 text-sm md:grid-cols-4"><p>Candidate: {trial ? `${trial.request.sleeves[0].lookback} bars · ${trial.status}` : 'No trial'}</p><p>Survival: {validation?.result ? Object.entries(validation.result.summary.counts).map(([k,v]) => `${v} ${k}`).join(' · ') : validation?.status ?? 'Not run'}</p><p>DSR: {numeric(selectionEvidence?.metrics.dsr as number | null)} · PBO: {numeric(selectionEvidence?.metrics.pbo as number | null)}</p><p>Diagnostic parameter attempts: {String(project.integrity.survival_parameter_attempts ?? 0)}</p></div><p className="mt-3 text-xs text-muted-foreground">DSR requires a defensible effective trial count; recorded trials do not establish the full research search history. Prospective records: {project.forward.length}. Risk and separate realized metrics are in MONITOR.</p></Panel>}
    <nav aria-label="Research lifecycle" className="flex flex-wrap gap-1 border-b pb-3">{stages.map(name => <Button key={name} size="sm" variant={stage === name ? 'secondary' : 'ghost'} aria-current={stage === name ? 'step' : undefined} onClick={() => setStage(name)} disabled={!project && !['THESIS', 'SIGNAL'].includes(name)}>{name}</Button>)}</nav>
    {project && stage === 'COMPARE' && <ProjectComparison key={project.id} project={project} candidateId={trialId} />}
    {(['THESIS', 'SIGNAL'] as string[]).includes(stage) && <><ProjectSpecification value={draft} onChange={setDraft} catalog={catalog} stage={stage as 'THESIS' | 'SIGNAL'} /><Field label="Reason for this revision"><Textarea aria-label="Reason for this revision" value={reason} onChange={e => setReason(e.target.value)} /></Field><Button disabled={busy} onClick={() => void save()}>{project ? 'Save new specification revision' : 'Create research project'}</Button></>}
    {project && stage === 'THESIS' && <Panel title="Literature and prior evidence" detail="References are researcher supplied. Flagship does not invent sources or replication findings."><div className="grid gap-3 md:grid-cols-2">{Object.keys(reference).map(key => <Field key={key} label={key}><Textarea aria-label={key} value={reference[key as keyof typeof reference]} onChange={e => setReference({ ...reference, [key]: e.target.value })} /></Field>)}</div><Button className="mt-3" disabled={busy} onClick={() => void post('/references', reference)}>Attach reference</Button><div className="mt-4 grid gap-2">{project.references.map((r, i) => <Detail key={i} label={String(r.citation)} value={r} />)}</div></Panel>}
    {project && !['THESIS', 'SIGNAL'].includes(stage) && <><Field label="Research decision / reason"><Textarea aria-label="Research decision / reason" value={reason} onChange={e => setReason(e.target.value)} /></Field>{dirty && <p className="text-sm text-amber-200">The editor has unsaved changes. Actions use the saved specification; save a new revision to change the experiment.</p>}</>}
    {project && stage === 'DATA' && <Panel title="Immutable dataset and research partition" detail="Capture uses the saved source/universe. The reserved final segment is excluded from every development trial."><Button disabled={busy || !!running} onClick={() => void post('/datasets', { reason })}>Capture dataset snapshot</Button>{project.datasets.map(d => <div className="mt-4 grid gap-3 rounded border p-4" key={d.id}><p className="break-all font-mono text-xs">{d.dataset_hash}</p><p className="text-sm">Development ends {d.partition.development_end.slice(0, 10)} · Reserved {d.partition.holdout_start.slice(0, 10)} to {d.partition.holdout_end.slice(0, 10)}</p><p className="text-sm text-amber-200">{d.partition.label}</p><Detail label="Data lineage" value={d.lineage} /></div>)}</Panel>}
    {project && ['EXPERIMENTS', 'VALIDATION', 'ROBUSTNESS', 'OOS', 'FREEZE'].includes(stage) && <Panel title="Candidate and evidence"><div className="grid gap-3 md:grid-cols-2"><Field label="Dataset snapshot"><select aria-label="Dataset snapshot" className="rounded border bg-background p-2" value={dataset} onChange={e => setDataset(e.target.value)}><option value="">Capture a dataset first</option>{project.datasets.map(d => <option key={d.id} value={d.id}>{d.created_at.slice(0, 19)} · {d.dataset_hash.slice(0, 12)}</option>)}</select></Field><Field label="Selected trial"><select aria-label="Selected trial" className="rounded border bg-background p-2" value={trialId} onChange={e => setTrialId(e.target.value)}><option value="">No trial selected</option>{project.trials.map(t => <option key={t.id} value={t.id}>{t.request.sleeves[0].lookback} bars · {t.request.rebalance} · {t.status} · {t.id.slice(0, 8)}</option>)}</select></Field></div>{trial && <p className="mt-3 text-sm text-muted-foreground">{trial.reason} {trial.post_oos ? 'WARNING: launched after OOS reveal.' : ''}</p>}</Panel>}
    {project && stage === 'EXPERIMENTS' && <><Panel title="Parameter experiments" detail="No winner is promoted automatically. Every submitted attempt is retained, including queue and calculation failures."><Field label="Lookbacks (comma separated; blank uses saved candidate)"><Input aria-label="Lookbacks (comma separated; blank uses saved candidate)" value={lookbacks} placeholder="63" onChange={e => setLookbacks(e.target.value)} /></Field><div className="my-3 flex gap-2"><Button variant="outline" disabled={busy || trial?.status !== 'completed'} onClick={() => void post(`/trials/${trialId}/decision`, {status: 'rejected', rationale: reason})}>Reject selected trial</Button><Button variant="outline" disabled={busy || trial?.status !== 'completed'} onClick={() => void post(`/trials/${trialId}/decision`, {status: 'watchlist', rationale: reason})}>Retain for review</Button></div><Button className="mt-3" disabled={busy || !dataset || dirty} onClick={() => void post('/trials', { revision_id: project.revision_id, dataset_id: dataset, reason, lookbacks: lookbacks.trim() ? lookbacks.split(',').map(Number) : [] })}>Run parameter experiments</Button><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Trial', 'Lookback', 'Status', 'Decision', 'Net return', 'Sharpe', 'Failure / reason'].map(t => <th className="p-2" key={t}>{t}</th>)}</tr></thead><tbody>{project.trials.map(t => <tr key={t.id} className="border-t"><td className="p-2"><button className="underline" onClick={() => setTrialId(t.id)}>{t.id.slice(0, 8)}</button></td><td className="p-2">{t.request.sleeves[0].lookback}</td><td className="p-2"><Status value={t.status} /></td><td className="p-2">{String([...project.journal].reverse().find(e => e.action === 'experiment_decision_recorded' && e.body.trial_id === t.id)?.body.status ?? 'Not reviewed')}</td><td className="p-2"><Pnl value={t.result?.metrics.total_return} /></td><td className="p-2">{numeric(t.result?.metrics.sharpe)}</td><td className="max-w-sm p-2">{t.error ?? t.reason}</td></tr>)}</tbody></table></div></Panel>{trial?.result && <Panel title="Development backtest" detail="Reserved final bars are excluded. These are historical modeled returns."><PerformancePlot data={trial.result.equity_curve} series={[{key: 'portfolio', label: 'Strategy portfolio', primary: true}, {key: 'benchmark', label: 'Benchmark'}]} /><Detail label="Complete stored backtest evidence" value={trial.result} /></Panel>}</>}
    {project && ['VALIDATION', 'ROBUSTNESS'].includes(stage) && <><Panel title={stage === 'VALIDATION' ? 'Strategy Survival validation' : 'Robustness and diagnostic regimes'} detail="Reuses Flagship's existing 18 layers. DSR remains unavailable without documented effective trials and IID assumptions."><Button disabled={busy || trial?.status !== 'completed'} onClick={() => void post(`/trials/${trialId}/validate`)}>Run existing Survival validation</Button>{validation && <div className="mt-3"><Status value={validation.status} />{validation.error && <p role="alert">{validation.error}</p>}{validation.result && <p className="mt-2 text-sm">{Object.entries(validation.result.summary.counts).map(([k, v]) => `${v} ${k}`).join(' · ')}</p>}</div>}<details className="mt-4"><summary className="text-sm">Versioned statistical protocol</summary><p className="my-2 text-xs text-muted-foreground">Saving changes creates a new revision. Configured gates use existing Survival semantics; prose acceptance criteria require researcher judgment.</p><Textarea aria-label="Survival protocol JSON" className="min-h-64 font-mono text-xs" value={protocolText} onChange={e => setProtocolText(e.target.value)} /><Button className="mt-2" onClick={() => { try { void save({...draft, validation: JSON.parse(protocolText)}); } catch { setError('Protocol must be valid JSON.'); } }} disabled={busy}>Save protocol revision</Button></details></Panel>{layers.map(l => <Panel key={l.id} title={`${l.id}. ${l.name}`} detail={l.methodology}><Status value={l.status} /><p className="my-3 text-sm text-muted-foreground">{l.assumptions}</p>{l.reasons.map((r, i) => <p className="mb-2 text-sm" key={i}>{r}</p>)}{l.id === 4 && <SensitivitySurface value={l.diagnostics.surface} />}<Detail label="Metrics and complete diagnostic surface" value={{ metrics: l.metrics, diagnostics: l.diagnostics }} /></Panel>)}</>}
    {project && stage === 'OOS' && <Panel title="Reserved final segment" detail="Reveal is permanent and recorded before computation. Public history cannot be certified as genuinely unseen outside Flagship.">{selectedData && <p className="mb-3 text-sm">{selectedData.partition.holdout_start.slice(0, 10)} → {selectedData.partition.holdout_end.slice(0, 10)} · {selectedData.partition.holdout_observations} observations</p>}<Button disabled={busy || trial?.status !== 'completed'} onClick={() => void post(`/trials/${trialId}/reveal`, { reason })}>Reveal reserved OOS and record access</Button>{project.oos.map(o => <div className="mt-4" key={o.id}><p className="mb-2 text-sm text-amber-200">{o.label}</p><Detail label={`OOS evidence · trial ${o.trial_id.slice(0, 8)}`} value={o} /></div>)}</Panel>}
    {project && stage === 'FREEZE' && <Panel title="Freeze a strategy version" detail="The selected trial must exactly match the current specification and completed validation. A freeze does not grant live execution permission."><div className="grid gap-3 md:grid-cols-2"><Field label="Expected metrics (JSON; researcher assumptions)"><Textarea aria-label="Expected metrics (JSON; researcher assumptions)" value={expected} onChange={e => setExpected(e.target.value)} placeholder={'{"sharpe": 0.5}'} /></Field><Field label="Basis for expectations"><Textarea aria-label="Basis for expectations" value={expectationBasis} onChange={e => setExpectationBasis(e.target.value)} /></Field><Field label="Kill criterion: maximum drawdown"><Input aria-label="Kill criterion: maximum drawdown" type="number" step=".01" value={killDrawdown} onChange={e => setKillDrawdown(+e.target.value)} /></Field><Field label="Kill criterion: maximum gross exposure"><Input aria-label="Kill criterion: maximum gross exposure" type="number" step=".1" value={killGross} onChange={e => setKillGross(+e.target.value)} /></Field><Field label="Stale evidence alert (days)"><Input aria-label="Stale evidence alert (days)" type="number" value={killStale} onChange={e => setKillStale(+e.target.value)} /></Field></div><Button className="mt-4" disabled={busy || !validation?.result || dirty} onClick={() => void perform(() => projectApi(`/${project.id}/freezes`, { trial_id: trialId, validation_id: validation!.id, reason, expected_metrics: JSON.parse(expected), expectation_basis: expectationBasis, kill: { max_drawdown: killDrawdown, max_gross: killGross, max_stale_days: killStale } }))}>Freeze candidate specification</Button>{project.freezes.map(f => <div key={f.id} className="mt-4"><p className="break-all font-mono text-xs">StrategyVersionID: {f.id}</p><Detail label={`Manifest · ${f.created_at}`} value={f} /></div>)}</Panel>}
    {project && ['FORWARD', 'MONITOR', 'PAPER'].includes(stage) && <Field label="Frozen strategy version"><select aria-label="Frozen strategy version" className="rounded border bg-background p-2" value={version} onChange={e => setVersion(e.target.value)}><option value="">Freeze a candidate first</option>{project.freezes.map(f => <option key={f.id} value={f.id}>{f.created_at.slice(0, 19)} · {f.id.slice(0, 12)}</option>)}</select></Field>}
    {project && stage === 'FORWARD' && <><Panel title="Prospective validation" detail="Each frozen version has its own forward record. Historical returns are never copied into it."><div className="grid gap-3 md:grid-cols-2"><Field label="Forward mode"><select aria-label="Forward mode" className="rounded border bg-background p-2" value={forwardMode} onChange={e => setForwardMode(e.target.value)}><option value="manual">User-recorded prospective protocol</option><option value="automated">Flagship simulated paper account</option></select></Field><Field label="Configured paper feed provider"><Input aria-label="Configured paper feed provider" value={provider} onChange={e => setProvider(e.target.value)} /></Field></div><Button className="mt-3" disabled={busy || !version} onClick={() => void post('/forward', { strategy_version_id: version, mode: forwardMode, provider, reason })}>Register frozen forward protocol</Button>{frozen?.synthetic && <p className="mt-3 text-sm text-amber-200">Synthetic demonstration: an empty protocol may be registered; market deployment and prospective marks are blocked.</p>}{comparison?.forward.map(f => <div className="mt-4 rounded border p-3" key={f.id}><p className="text-sm">{f.source} · {f.observations} observations · {f.as_of ?? 'No observations yet'}</p><p className="my-2 break-all font-mono text-xs">Record: {f.record_id}</p>{f.mode === 'automated' && <div className="flex flex-wrap gap-2">{['activate', 'pause', 'resume', 'stop'].map(action => <Button key={action} variant="outline" disabled={busy} onClick={() => void post(`/forward/${f.id}/control`, { action })}>{action}</Button>)}</div>}</div>)}</Panel>{selectedForward?.mode === 'manual' && !frozen?.synthetic && <Panel title="Record actual prospective evidence" detail="Timestamps must advance and marks must follow receipt of a recorded signal. User records remain unverified by a broker."><div className="grid gap-3 md:grid-cols-2"><Field label="Event kind"><select aria-label="Event kind" className="rounded border bg-background p-2" value={eventKind} onChange={e => setEventKind(e.target.value)}><option>signal</option><option>observation</option></select></Field><Field label="Observed timestamp (UTC ISO)"><Input aria-label="Observed timestamp (UTC ISO)" value={observedAt} placeholder="2026-10-05T15:00:00Z" onChange={e => setObservedAt(e.target.value)} /></Field><Field label="Weights (JSON)"><Textarea aria-label="Weights (JSON)" value={eventWeights} onChange={e => setEventWeights(e.target.value)} /></Field><Field label="Costs (bps)"><Input aria-label="Costs (bps)" type="number" value={eventCost} onChange={e => setEventCost(+e.target.value)} /></Field>{eventKind === 'observation' && <><Field label="Previously recorded signal"><select aria-label="Previously recorded signal" className="rounded border bg-background p-2" value={signalId} onChange={e => setSignalId(e.target.value)}><option value="">Choose signal</option>{selectedForward.events.filter(e => e.kind === 'signal').map(e => <option key={e.id} value={e.id}>{e.observed_at}</option>)}</select></Field><Field label="Marked NAV"><Input aria-label="Marked NAV" type="number" value={eventNav} onChange={e => setEventNav(+e.target.value)} /></Field></>}</div><Button className="mt-3" disabled={busy} onClick={() => void perform(() => projectApi(`/${project.id}/forward/${selectedForward.id}/events`, { kind: eventKind, observed_at: observedAt, weights: JSON.parse(eventWeights), cost_bps: eventCost, ...(eventKind === 'observation' ? { signal_id: signalId, nav: eventNav } : {}) }))}>Record prospective event</Button></Panel>}</>}
    {project && stage === 'MONITOR' && <Panel title="Expected versus realized" detail="Review separate historical, walk-forward, reserved OOS and prospective periods. Alerts do not issue broker orders.">{comparison ? <><p className="mb-3 text-sm">{comparison.expectation_basis}</p><Detail label="Prespecified expected metrics" value={comparison.expected} /><div className="my-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Metric', 'Historical development', 'Walk-forward', 'Reserved OOS', 'Prospective'].map(t => <th className="p-2" key={t}>{t}</th>)}</tr></thead><tbody>{comparison.table.map(r => <tr key={r.metric} className="border-t"><td className="p-2">{r.metric}</td>{(['historical', 'walk_forward', 'reserved_oos', 'prospective'] as const).map(k => <td className="p-2" key={k}>{['total_return', 'cagr', 'max_drawdown'].includes(r.metric) ? <Pnl value={r[k]} /> : numeric(r[k])}</td>)}</tr>)}</tbody></table></div>{comparison.alerts.length ? comparison.alerts.map((a, i) => <p key={i} className="mb-2 text-sm text-red-200" role="alert">Review required: {a.kind} · {a.value ?? ''} / {a.limit ?? ''}</p>) : <p className="my-3 text-sm">No threshold breach recorded. Missing observations do not establish safety or strategy survival.</p>}{comparison.limitations.map((l, i) => <p className="mb-2 text-xs text-muted-foreground" key={i}>{l}</p>)}</> : <p className="text-sm text-muted-foreground">Select a frozen version to compare evidence. No prospective values are manufactured.</p>}</Panel>}
    {project && stage === 'PAPER' && <Panel title="Research paper and reproducibility package" detail="21 sections assemble authored thesis, literature, retained attempts, statistical evidence, OOS access and forward records. Conclusions remain researcher-written."><div className="flex flex-wrap gap-3"><a className="rounded border px-4 py-2 text-sm" href={`/integrations/engine/api/research/projects/${project.id}/report`} download>Download research paper (Markdown)</a><a className="rounded border px-4 py-2 text-sm" href={`/integrations/engine/api/research/projects/${project.id}/export`} download>Download reproducibility ZIP</a></div><p className="mt-4 text-sm text-muted-foreground">Unrevealed final bars are excluded from exports. Development snapshots and nested Survival exports preserve replay. New revisions never replace an earlier frozen specification.</p></Panel>}
    {project && <><Panel title="Research decision journal" detail="Reasons, inspections, failures, reveals and freezes remain visible."><Button variant="outline" disabled={busy} onClick={() => void post('/notes', { reason })}>Append research note</Button><div className="mt-3 max-h-96 space-y-2 overflow-auto">{[...project.journal].reverse().map((e, i) => <Detail key={i} label={`${e.created.slice(0, 19)} UTC · ${e.action.replaceAll('_', ' ')}`} value={e.body} />)}</div></Panel>{project.tasks.some(t => t.status === 'failed') && <Panel title="Retained failed tasks">{project.tasks.filter(t => t.status === 'failed').map(t => <Detail key={t.id} label={t.kind} value={t.outcome} />)}</Panel>}</>}
  </section>;
}

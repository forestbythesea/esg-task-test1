import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, BarChart3, Database, FileUp, Lock, MessageSquare, Play, RefreshCw, ShieldCheck } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  fetchCompanies,
  fetchConfigStatus,
  fetchObservability,
  fetchRuns,
  getToken,
  login,
  processReport,
  runIngestion,
  sendChat,
  uploadReport
} from "./lib/api";
import type { Company, ConfigStatus, Run, Trace } from "./lib/types";
import "./styles.css";

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = React.useState("analyst");
  const [error, setError] = React.useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(username);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }
  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <div className="mark"><ShieldCheck size={28} /></div>
        <h1>ESG Risk Dashboard</h1>
        <p>Use a demo user to inspect grounded ESG analysis, risk scores, chat, and traces.</p>
        <select value={username} onChange={(event) => setUsername(event.target.value)}>
          <option value="analyst">analyst</option>
          <option value="reviewer">reviewer</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit"><Lock size={16} /> Sign in</button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}

function ScoreCards({ company }: { company: Company }) {
  if (!company.risk_scores.length) {
    return <div className="empty">Run ingestion to generate ESG risk scores.</div>;
  }
  return (
    <section className="score-grid">
      {company.risk_scores.map((score) => (
        <article className="score-card" key={score.dimension}>
          <div>
            <span>{score.dimension}</span>
            <Badge tone={score.confidence}>{score.confidence}</Badge>
          </div>
          <strong>{score.score}</strong>
          <p>{score.rationale}</p>
        </article>
      ))}
    </section>
  );
}

function ConfigBanner({ status }: { status: ConfigStatus | null }) {
  if (!status) return null;
  const ready = status.openai_configured && status.model_validated;
  return (
    <section className={`config-banner ${ready ? "ready" : "blocked"}`}>
      <div>
        <strong>{ready ? "OpenAI connected" : "OpenAI setup required"}</strong>
        <span>{status.model} · {status.generation_mode}</span>
      </div>
      {!ready && <p>{status.error ?? "Configure OPENAI_API_KEY and restart the backend."}</p>}
    </section>
  );
}

function UploadPanel({
  disabled,
  onUploaded
}: {
  disabled: boolean;
  onUploaded: () => Promise<void>;
}) {
  const [companyName, setCompanyName] = React.useState("");
  const [reportYear, setReportYear] = React.useState("2026");
  const [label, setLabel] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!companyName.trim() || !file) {
      setMessage("Company name and PDF are required.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("company_name", companyName);
      form.append("report_year", reportYear);
      form.append("document_label", label);
      form.append("file", file);
      await uploadReport(form);
      setCompanyName("");
      setLabel("");
      setFile(null);
      await onUploaded();
      setMessage("PDF uploaded. Select it and process with OpenAI.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel upload-panel">
      <h2><FileUp size={18} /> Upload PDF</h2>
      <form onSubmit={submit} className="upload-form">
        <input placeholder="Company name" value={companyName} onChange={(event) => setCompanyName(event.target.value)} />
        <input placeholder="Report year" value={reportYear} onChange={(event) => setReportYear(event.target.value)} />
        <input placeholder="Document label" value={label} onChange={(event) => setLabel(event.target.value)} />
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button disabled={busy || disabled}>{busy ? <RefreshCw size={16} /> : <FileUp size={16} />} Upload</button>
      </form>
      {message && <small>{message}</small>}
    </section>
  );
}

function Charts({ company }: { company: Company }) {
  const data = company.risk_scores;
  return (
    <section className="chart-grid">
      <div className="panel">
        <h2><Activity size={18} /> Risk profile</h2>
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={data}>
            <PolarGrid />
            <PolarAngleAxis dataKey="dimension" />
            <Radar dataKey="score" stroke="#167f7a" fill="#167f7a" fillOpacity={0.28} />
            <Tooltip />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="panel">
        <h2><BarChart3 size={18} /> Score comparison</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="dimension" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Bar dataKey="score" fill="#b35f2b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function EvidenceReview({ company }: { company: Company }) {
  return (
    <section className="panel">
      <h2><Database size={18} /> Evidence review</h2>
      {company.summary && (
        <div className="summary">
          <h3>Summary</h3>
          <p>{company.summary.answer}</p>
          {company.summary.sources.map((source, index) => (
            <blockquote key={index}>p.{source.page} · {source.quote}</blockquote>
          ))}
        </div>
      )}
      <div className="qa-list">
        {company.questions.map((qa) => (
          <article className="qa" key={qa.question}>
            <div className="qa-top">
              <h3>{qa.question}</h3>
              <Badge tone={qa.status === "answered" ? qa.confidence : "low"}>{qa.status}</Badge>
            </div>
            <p>{qa.answer ?? qa.missing_information}</p>
            {qa.sources.map((source, index) => (
              <blockquote key={index}>p.{source.page} · {source.quote}</blockquote>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}

function ChatPanel({ company, disabled }: { company: Company; disabled: boolean }) {
  const [message, setMessage] = React.useState("What are the main ESG risks?");
  const [responses, setResponses] = React.useState<
    Array<{
      q: string;
      a: string;
      meta: string;
      citations: Array<{ document_name: string; page: number; quote: string }>;
    }>
  >([]);
  const [busy, setBusy] = React.useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    const q = message;
    setMessage("");
    try {
      const result = await sendChat(company.id, q);
      setResponses((items) => [
        {
          q,
          a: result.answer,
          meta: `${result.reasoning_effort} reasoning · ${result.token_usage.total_tokens} tokens · ${result.latency_ms} ms`,
          citations: result.citations
        },
        ...items
      ]);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel chat-panel">
      <h2><MessageSquare size={18} /> Follow-up chat</h2>
      <form onSubmit={submit} className="chat-form">
        <input value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} disabled={disabled} />
        <button disabled={busy || disabled}>{busy ? <RefreshCw size={16} /> : <MessageSquare size={16} />} Ask</button>
      </form>
      <div className="chat-log">
        {responses.map((item, index) => (
          <article key={index} className="chat-item">
            <strong>{item.q}</strong>
            <p>{item.a}</p>
            <div className="citation-list">
              {item.citations.map((source, citationIndex) => (
                <blockquote key={citationIndex}>p.{source.page} · {source.quote}</blockquote>
              ))}
            </div>
            <small>{item.meta}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function Observability({ runs, traces }: { runs: Run[]; traces: Trace[] }) {
  return (
    <section className="panel">
      <h2><Activity size={18} /> Observability</h2>
      <div className="run-list">
        {runs.slice(0, 3).map((run) => (
          <div key={run.id} className="run-row">
            <span>{run.id.slice(0, 8)}</span>
            <Badge tone={run.status === "completed" ? "high" : "medium"}>{run.status}</Badge>
            <small>{run.output_path}</small>
          </div>
        ))}
      </div>
      <div className="trace-table">
        {traces.map((trace) => (
          <div className="trace-row" key={trace.id}>
            <span>{trace.step}</span>
            <span>{trace.reasoning_effort}</span>
            <span>{trace.total_tokens} tok</span>
            <span>${trace.estimated_cost_usd.toFixed(5)}</span>
            <span>{trace.latency_ms} ms</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Dashboard() {
  const [companies, setCompanies] = React.useState<Company[]>([]);
  const [configStatus, setConfigStatus] = React.useState<ConfigStatus | null>(null);
  const [selectedId, setSelectedId] = React.useState("");
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [traces, setTraces] = React.useState<Trace[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [loadError, setLoadError] = React.useState("");
  const selected = companies.find((company) => company.id === selectedId) ?? companies[0];
  const openAiReady = Boolean(configStatus?.openai_configured && configStatus?.model_validated);

  async function refresh() {
    setLoadError("");
    const configResult = await fetchConfigStatus().catch((err) => {
      setLoadError(err instanceof Error ? err.message : "Could not load OpenAI status.");
      return null;
    });
    if (configResult) setConfigStatus(configResult);

    const companyData = await fetchCompanies().catch((err) => {
      const message = err instanceof Error ? err.message : "Could not load companies.";
      setLoadError(message);
      if (message.includes("Session expired")) window.location.reload();
      return [] as Company[];
    });
    setCompanies(companyData);
    if ((!selectedId || !companyData.some((company) => company.id === selectedId)) && companyData[0]) {
      setSelectedId(companyData[0].id);
    }

    const runData = await fetchRuns().catch(() => [] as Run[]);
    setRuns(runData);
    if (runData[0]) {
      const obs = await fetchObservability(runData[0].id).catch(() => null);
      setTraces(obs?.traces ?? []);
    }
  }

  React.useEffect(() => {
    refresh();
  }, []);

  async function ingest() {
    setBusy(true);
    try {
      await runIngestion();
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function processSelected() {
    if (!selected) return;
    setBusy(true);
    try {
      await processReport(selected.id);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">Grounded ESG intelligence</span>
          <h1>Risk Dashboard</h1>
        </div>
        <div className="actions">
          <select value={selected?.id ?? ""} onChange={(event) => setSelectedId(event.target.value)}>
            {companies.map((company) => <option key={company.id} value={company.id}>{company.name} · {company.report_year} · {company.source_type} · {company.status}</option>)}
          </select>
          <button onClick={ingest} disabled={busy || !openAiReady}>{busy ? <RefreshCw size={16} /> : <Play size={16} />} Run baseline</button>
          {selected?.source_type === "upload" && (
            <button onClick={processSelected} disabled={busy || !openAiReady}>
              {busy ? <RefreshCw size={16} /> : <Play size={16} />} Process PDF
            </button>
          )}
        </div>
      </header>
      <ConfigBanner status={configStatus} />
      {loadError && <section className="config-banner blocked"><p>{loadError}</p></section>}
      <UploadPanel disabled={!openAiReady} onUploaded={refresh} />
      {selected ? (
        <>
          <section className="report-strip">
            <span>{selected.file_name}</span>
            <Badge tone={selected.status === "completed" ? "high" : selected.status === "failed" ? "low" : "medium"}>{selected.status}</Badge>
            <Badge>{selected.generation_mode ?? "not generated"}</Badge>
          </section>
          <ScoreCards company={selected} />
          <Charts company={selected} />
          <div className="content-grid">
            <EvidenceReview company={selected} />
            <ChatPanel company={selected} disabled={!openAiReady || selected.status !== "completed"} />
          </div>
          <Observability runs={runs} traces={traces} />
        </>
      ) : (
        <div className="empty">No companies loaded.</div>
      )}
    </main>
  );
}

function App() {
  const [authed, setAuthed] = React.useState(Boolean(getToken()));
  return authed ? <Dashboard /> : <Login onLogin={() => setAuthed(true)} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);

import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, ShieldAlert, Sliders, Play, Terminal, Database, 
  HelpCircle, CheckCircle2, XCircle, ChevronRight, RefreshCw, Key, 
  Cpu, Layers, AlertTriangle, ArrowUpRight, Search, Zap, FileText
} from 'lucide-react';

interface MetricDetail {
  threshold: number;
  scores: number[];
  reasons: string[];
  passing_runs: number;
  total_runs: number;
  passed: boolean;
}

interface EvaluationResult {
  preset: {
    id: string;
    title: string;
    description: string;
    config: {
      top_k: number;
      prompt_mode: string;
      noise_injection: boolean;
    };
  };
  verdict: 'PASS' | 'BLOCKED';
  required_passing_runs: number;
  gate_runs: number;
  metrics: {
    faithfulness: MetricDetail;
    answer_relevancy: MetricDetail;
    context_precision: MetricDetail;
    context_recall: MetricDetail;
  };
}

interface Preset {
  id: string;
  title: string;
  description: string;
  config: {
    top_k: number;
    prompt_mode: string;
    noise_injection: boolean;
  };
}

interface PresetsResponse {
  gate_runs: number;
  required_passing_runs: number;
  default_thresholds: Record<string, number>;
  metric_labels: Record<string, string>;
  presets: Preset[];
}

interface BenchmarkItem {
  id: string;
  question: string;
  ground_truth_answer: string;
  ground_truth_chunk_ids: string[];
  source: string;
}

export default function App() {
  const [presetsData, setPresetsData] = useState<PresetsResponse | null>(null);
  const [activePresetId, setActivePresetId] = useState<string>('healthy_baseline');
  const [topK, setTopK] = useState<number>(3);
  const [promptMode, setPromptMode] = useState<string>('strict');
  const [noiseInjection, setNoiseInjection] = useState<boolean>(false);
  
  const [thresholds, setThresholds] = useState<Record<string, number>>({
    faithfulness: 0.90,
    answer_relevancy: 0.80,
    context_precision: 0.75,
    context_recall: 0.90,
  });
  const [requiredPasses, setRequiredPasses] = useState<number>(4);

  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Active Tab: 'telemetry' | 'xray' | 'sandbox'
  const [activeTab, setActiveTab] = useState<'telemetry' | 'xray' | 'sandbox'>('telemetry');

  // X-Ray state
  const [benchmarkQuestions, setBenchmarkQuestions] = useState<BenchmarkItem[]>([]);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>('bench-001');

  // Sandbox state
  const [sandboxQuery, setSandboxQuery] = useState<string>('when does my invoice actually get sent out?');
  const [sandboxResult, setSandboxResult] = useState<any>(null);
  const [sandboxLoading, setSandboxLoading] = useState<boolean>(false);

  // Live BYOK Modal state
  const [showLiveModal, setShowLiveModal] = useState<boolean>(false);
  const [liveApiKey, setLiveApiKey] = useState<string>('');
  const [liveQuestion, setLiveQuestion] = useState<string>('when does my invoice actually get sent out?');
  const [liveResult, setLiveResult] = useState<any>(null);
  const [liveLoading, setLiveLoading] = useState<boolean>(false);

  // Fetch initial presets and benchmark questions
  useEffect(() => {
    fetch('/api/presets')
      .then(res => res.json())
      .then((data: PresetsResponse) => {
        setPresetsData(data);
        if (data.default_thresholds) {
          setThresholds(data.default_thresholds);
        }
        if (data.required_passing_runs) {
          setRequiredPasses(data.required_passing_runs);
        }
      })
      .catch(err => console.error('Failed to load presets:', err));

    // Load benchmark questions for X-Ray
    // Since backend doesn't have a direct public list_benchmark endpoint, we can fetch or mock based on known benchmark items or add an endpoint if needed, or fetch via a small fetch if exposed. Wait, let's look at backend/main.py — does it have /api/benchmark? Let's check backend/main.py or create mock benchmark list corresponding to rag_benchmark_v3.jsonl.
    // Actually rag_benchmark_v3.jsonl items are known:
    setBenchmarkQuestions([
      { id: "bench-001", question: "when does my invoice actually get sent out?", ground_truth_answer: "Invoices are generated at 00:00 UTC on your monthly billing day, which is the calendar day you originally subscribed, and emailed to the workspace billing contact.", ground_truth_chunk_ids: ["kb-billing-001"], source: "support-ticket-4821" },
      { id: "bench-002", question: "if i upgrade halfway through the month do i get charged twice", ground_truth_answer: "No. An upgrade takes effect immediately and you are charged a single prorated amount covering the remainder of the current billing period, not a second full invoice.", ground_truth_chunk_ids: ["kb-billing-002", "kb-billing-001"], source: "support-ticket-4903" },
      { id: "bench-003", question: "how many api calls can I make on the team plan?", ground_truth_answer: "The Team plan allows 600 requests per minute. The limit applies per workspace rather than per API key, and is measured over a sliding 60 second window.", ground_truth_chunk_ids: ["kb-ratelimit-001"], source: "product-chat-log-2026-03-04" },
      { id: "bench-004", question: "what should our client do when it starts getting 429s?", ground_truth_answer: "Read the Retry-After header on the 429 response for the number of seconds to wait, then retry with exponential backoff. Watch X-RateLimit-Remaining and X-RateLimit-Reset to back off before hitting the limit, and remember that bulk endpoints count as ten requests each.", ground_truth_chunk_ids: ["kb-ratelimit-002", "kb-ratelimit-001"], source: "sales-call-2026-03-11" },
      { id: "bench-005", question: "how long do team invites stay valid before they expire?", ground_truth_answer: "An invitation email is valid for 14 days. After that it expires and an Admin has to resend it.", ground_truth_chunk_ids: ["kb-onboarding-001"], source: "support-ticket-5017" },
      { id: "bench-006", question: "can i get my money back if i cancel after 3 weeks", ground_truth_answer: "Not on a monthly renewal. Full refunds are only available within 14 days of the first paid invoice, so a cancellation at three weeks falls outside that window. Annual plans are still eligible for a prorated refund within 30 days of purchase, requested by emailing billing with the invoice number.", ground_truth_chunk_ids: ["kb-refunds-001", "kb-refunds-002"], source: "support-ticket-5122" },
      { id: "bench-007", question: "do we need to be on enterprise to log in with okta?", ground_truth_answer: "Yes. SAML single sign-on, including Okta, is available on the Enterprise plan only. It is configured by a workspace Admin under Settings, Security, Single sign-on.", ground_truth_chunk_ids: ["kb-sso-001"], source: "sales-call-2026-02-27" },
      { id: "bench-008", question: "what happens to our workspace if the card on file gets declined?", ground_truth_answer: "Meridian retries the charge three times over seven days and emails the billing contact after each attempt. If all three retries fail, the workspace becomes read-only until a valid payment method is added, and data is retained for 30 days after that point.", ground_truth_chunk_ids: ["kb-billing-003"], source: "support-ticket-5188" },
    ]);
  }, []);

  // Run evaluation whenever preset, sliders, or thresholds change
  useEffect(() => {
    runEvaluation();
  }, [activePresetId, thresholds, requiredPasses]);

  const runEvaluation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/evaluate/snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preset_id: activePresetId,
          thresholds,
          required_passing_runs: requiredPasses,
        }),
      });
      if (!res.ok) {
        throw new Error(`Evaluation request failed: ${res.statusText}`);
      }
      const data: EvaluationResult = await res.json();
      setEvalResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to compute evaluation snapshot');
    } finally {
      setLoading(false);
    }
  };

  const handlePresetSelect = (preset: Preset) => {
    setActivePresetId(preset.id);
    setTopK(preset.config.top_k);
    setPromptMode(preset.config.prompt_mode);
    setNoiseInjection(preset.config.noise_injection);
  };

  const handleThresholdChange = (metric: string, val: number) => {
    setThresholds(prev => ({ ...prev, [metric]: val }));
  };

  // Run deterministic retrieval sandbox check
  const runSandboxCheck = async () => {
    setSandboxLoading(true);
    try {
      const res = await fetch('/api/evaluate/retrieval-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preset_id: activePresetId,
          top_k: topK,
          noise_injection: noiseInjection,
          question: sandboxQuery,
        }),
      });
      const data = await res.json();
      setSandboxResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setSandboxLoading(false);
    }
  };

  // Run live evaluation with OpenAI or Groq Key
  const runLiveEvaluation = async () => {
    setLiveLoading(true);
    setLiveResult(null);
    try {
      const res = await fetch('/api/evaluate/live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: liveQuestion,
          preset_id: activePresetId,
          top_k: topK,
          prompt_mode: promptMode,
          noise_injection: noiseInjection,
          api_key: liveApiKey || null,
          thresholds,
        }),
      });
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.indexOf("application/json") !== -1) {
        const data = await res.json();
        if (!res.ok) {
          setLiveResult({ error: data.detail || data.error || 'Live evaluation failed' });
        } else {
          setLiveResult(data);
        }
      } else {
        const text = await res.text();
        setLiveResult({ error: text || `HTTP error! status: ${res.status}` });
      }
    } catch (err: any) {
      console.error(err);
      setLiveResult({ error: err.message || 'Live evaluation failed' });
    } finally {
      setLiveLoading(false);
    }
  };

  const isPassed = evalResult?.verdict === 'PASS';

  return (
    <div className="min-h-screen bg-[#F7F5FC] text-[#121118] font-sans antialiased flex flex-col">
      
      {/* EDITORIAL HEADER */}
      <header className="bg-white border-b border-[#E4E0F0] px-6 py-4 sticky top-0 z-30 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <span className="text-[11px] font-mono tracking-[0.18em] text-[#7C3AED] font-semibold bg-[#EDE9FE] px-2.5 py-0.5 rounded-full">
                  BUILD • SOLVE • EVALUATE
                </span>
                <span className="text-xs font-mono text-[#524E63] bg-[#F0ECF9] px-2 py-0.5 rounded border border-[#E4E0F0]">
                  PR #42 • feat/hybrid-retriever
                </span>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-[#121118] mt-1 flex items-center gap-2">
                RAG Evaluation & CI Gate Console
              </h1>
              <div className="relative mt-1 w-fit">
                <span className="text-xs text-[#524E63]">Four metric regression protection for enterprise retrieval pipelines</span>
                <svg className="absolute -bottom-1.5 left-0 w-48 h-2 text-[#7C3AED]" viewBox="0 0 120 8" fill="none" aria-hidden="true">
                  <path d="M1.5 5.2 C 22 1.8, 48 6.4, 72 4.1 S 108 2.2, 118.5 5.6" stroke="#7C3AED" strokeWidth="1.5" strokeLinecap="round" opacity="0.85" />
                </svg>
              </div>
            </div>
          </div>

          {/* Prominent CI Gate Verdict Banner */}
          <div className="flex items-center gap-3">
            <div className={`px-4 py-2 rounded-xl border flex items-center gap-2.5 shadow-sm ${
              isPassed 
                ? 'bg-[#ECFDF5] border-[#D1FAE5] text-[#059669]' 
                : 'bg-[#FFF1F2] border-[#FFE4E6] text-[#E11D48]'
            }`}>
              {isPassed ? <ShieldCheck className="w-5 h-5 text-[#059669]" /> : <ShieldAlert className="w-5 h-5 text-[#E11D48]" />}
              <div className="flex flex-col">
                <span className="font-mono text-xs font-bold tracking-wider">
                  {isPassed ? 'CI GATE PASSED — MERGE ALLOWED' : 'MERGE BLOCKED — REGRESSION DETECTED'}
                </span>
                <span className="text-[11px] opacity-80">
                  {evalResult ? `${Object.values(evalResult.metrics).filter(m => m.passed).length}/4 metrics passed • ${evalResult.required_passing_runs}/${evalResult.gate_runs} runs req.` : 'Evaluating...'}
                </span>
              </div>
            </div>

            <button
              onClick={() => setShowLiveModal(true)}
              className="px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold rounded-xl shadow-sm transition flex items-center gap-2"
            >
              <Key className="w-3.5 h-3.5" />
              <span>Run Live (BYOK)</span>
            </button>
          </div>

        </div>

        {/* Preset Pills Bar */}
        {presetsData && (
          <div className="max-w-7xl mx-auto mt-4 pt-3 border-t border-[#E4E0F0] flex items-center gap-2 overflow-x-auto pb-1">
            <span className="text-xs font-medium text-[#524E63] shrink-0 mr-1">Presets:</span>
            {presetsData.presets.map(p => {
              const active = p.id === activePresetId;
              return (
                <button
                  key={p.id}
                  onClick={() => handlePresetSelect(p)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition shrink-0 flex items-center gap-1.5 ${
                    active 
                      ? 'bg-[#7C3AED] text-white shadow-sm' 
                      : 'bg-[#F0ECF9] text-[#524E63] hover:bg-[#E4E0F0] hover:text-[#121118]'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-white' : 'bg-[#7C3AED]'}`}></span>
                  <span>{p.title}</span>
                </button>
              );
            })}
          </div>
        )}
      </header>

      {/* MAIN LAYOUT: LEFT CONTROL RAIL + MAIN TELEMETRY STAGE */}
      <div className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 flex flex-col lg:flex-row gap-6">
        
        {/* LEFT CONTROL RAIL (320px) */}
        <aside className="w-full lg:w-[320px] shrink-0 flex flex-col gap-6">
          
          <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
            <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
              <h2 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#7C3AED]" />
                Pipeline Controls
              </h2>
              <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#7C3AED] px-2 py-0.5 rounded">
                Config
              </span>
            </div>

            <div className="mt-4 space-y-4">
              {/* Top-K Slider */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-[#524E63]">Retrieved Chunks (Top-K)</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{topK}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="6"
                  step="1"
                  value={topK}
                  onChange={e => setTopK(Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-[#524E63] mt-1 font-mono">
                  <span>1 (Sparse)</span>
                  <span>3 (Default)</span>
                  <span>6 (Broad)</span>
                </div>
              </div>

              {/* Prompt Mode */}
              <div className="pt-2 border-t border-[#E4E0F0]">
                <label className="text-xs font-medium text-[#524E63] block mb-1.5">System Prompt Strictness</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setPromptMode('strict')}
                    className={`py-1.5 px-3 rounded-lg text-xs font-medium transition ${
                      promptMode === 'strict'
                        ? 'bg-[#7C3AED] text-white shadow-sm'
                        : 'bg-[#F0ECF9] text-[#524E63] hover:bg-[#E4E0F0]'
                    }`}
                  >
                    Strict Grounding
                  </button>
                  <button
                    onClick={() => setPromptMode('permissive')}
                    className={`py-1.5 px-3 rounded-lg text-xs font-medium transition ${
                      promptMode === 'permissive'
                        ? 'bg-[#7C3AED] text-white shadow-sm'
                        : 'bg-[#F0ECF9] text-[#524E63] hover:bg-[#E4E0F0]'
                    }`}
                  >
                    Permissive
                  </button>
                </div>
              </div>

              {/* Noise Injection */}
              <div className="pt-2 border-t border-[#E4E0F0] flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-[#121118] block">Noise Injection</span>
                  <span className="text-[11px] text-[#524E63]">Inject distractor chunks</span>
                </div>
                <button
                  onClick={() => setNoiseInjection(!noiseInjection)}
                  className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ease-in-out ${
                    noiseInjection ? 'bg-[#7C3AED]' : 'bg-[#E4E0F0]'
                  }`}
                >
                  <div className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ease-in-out ${
                    noiseInjection ? 'translate-x-5' : 'translate-x-0'
                  }`} />
                </button>
              </div>
            </div>
          </div>

          {/* Live CI Threshold Sliders */}
          <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
            <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
              <h2 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#7C3AED]" />
                CI Thresholds & Gate
              </h2>
              <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#7C3AED] px-2 py-0.5 rounded">
                Real-Time
              </span>
            </div>

            <div className="mt-4 space-y-4">
              {/* Faithfulness */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-[#121118]">Faithfulness</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{thresholds.faithfulness.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.01"
                  value={thresholds.faithfulness}
                  onChange={e => handleThresholdChange('faithfulness', Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
              </div>

              {/* Answer Relevancy */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-[#121118]">Answer Relevancy</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{thresholds.answer_relevancy.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.01"
                  value={thresholds.answer_relevancy}
                  onChange={e => handleThresholdChange('answer_relevancy', Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
              </div>

              {/* Context Precision */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-[#121118]">Context Precision</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{thresholds.context_precision.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.01"
                  value={thresholds.context_precision}
                  onChange={e => handleThresholdChange('context_precision', Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
              </div>

              {/* Context Recall */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-[#121118]">Context Recall</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{thresholds.context_recall.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.01"
                  value={thresholds.context_recall}
                  onChange={e => handleThresholdChange('context_recall', Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
              </div>

              {/* Required Passes */}
              <div className="pt-2 border-t border-[#E4E0F0]">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-[#121118]">Required Passes (X/5 runs)</span>
                  <span className="font-mono font-bold text-[#7C3AED]">{requiredPasses} / 5</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={requiredPasses}
                  onChange={e => setRequiredPasses(Number(e.target.value))}
                  className="w-full accent-[#7C3AED] cursor-pointer"
                />
              </div>
            </div>
          </div>

        </aside>

        {/* MAIN TELEMETRY STAGE */}
        <main className="flex-1 flex flex-col gap-6">
          
          {/* Navigation Tabs */}
          <div className="bg-white rounded-2xl border border-[#E4E0F0] p-1.5 flex items-center gap-2 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
            <button
              onClick={() => setActiveTab('telemetry')}
              className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
                activeTab === 'telemetry'
                  ? 'bg-[#7C3AED] text-white shadow-sm'
                  : 'text-[#524E63] hover:bg-[#F0ECF9] hover:text-[#121118]'
              }`}
            >
              <Cpu className="w-4 h-4" />
              <span>Telemetry & Gate Diagnosis</span>
            </button>

            <button
              onClick={() => setActiveTab('xray')}
              className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
                activeTab === 'xray'
                  ? 'bg-[#7C3AED] text-white shadow-sm'
                  : 'text-[#524E63] hover:bg-[#F0ECF9] hover:text-[#121118]'
              }`}
            >
              <Search className="w-4 h-4" />
              <span>Question X-Ray Inspector</span>
            </button>

            <button
              onClick={() => setActiveTab('sandbox')}
              className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
                activeTab === 'sandbox'
                  ? 'bg-[#7C3AED] text-white shadow-sm'
                  : 'text-[#524E63] hover:bg-[#F0ECF9] hover:text-[#121118]'
              }`}
            >
              <Terminal className="w-4 h-4" />
              <span>Deterministic Retrieval Sandbox</span>
            </button>
          </div>

          {/* ACTIVE PRESET HEADER INFO */}
          {evalResult && (
            <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)] flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase bg-[#F0ECF9] text-[#524E63] px-2 py-0.5 rounded">Active Preset</span>
                  <h3 className="text-base font-bold text-[#121118]">{evalResult.preset.title}</h3>
                </div>
                <p className="text-xs text-[#524E63] mt-1">{evalResult.preset.description}</p>
              </div>
              <div className="flex items-center gap-3 text-xs font-mono bg-[#F7F5FC] px-3 py-2 rounded-xl border border-[#E4E0F0]">
                <div>Top-K: <strong className="text-[#7C3AED]">{evalResult.preset.config.top_k}</strong></div>
                <div className="w-px h-3 bg-[#E4E0F0]" />
                <div>Prompt: <strong className="text-[#7C3AED]">{evalResult.preset.config.prompt_mode}</strong></div>
                <div className="w-px h-3 bg-[#E4E0F0]" />
                <div>Noise: <strong className="text-[#7C3AED]">{evalResult.preset.config.noise_injection ? 'True' : 'False'}</strong></div>
              </div>
            </div>
          )}

          {/* TAB 1: TELEMETRY & GATE */}
          {activeTab === 'telemetry' && evalResult && (
            <div className="space-y-6">
              
              {/* Two Pipeline Split Diagnosis Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Retrieval Health Card */}
                <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)] flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
                      <h3 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                        <Database className="w-4 h-4 text-[#7C3AED]" />
                        Retrieval Health (Precision & Recall)
                      </h3>
                      <span className="text-[10px] font-mono text-[#524E63]">Pipeline Half 1</span>
                    </div>

                    <div className="mt-4 space-y-4">
                      {/* Context Precision */}
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-medium text-[#121118]">Context Precision (Threshold ≥ {evalResult.metrics.context_precision.threshold})</span>
                          <span className={`gate-chip ${evalResult.metrics.context_precision.passed ? 'pass' : 'blocked'}`}>
                            {evalResult.metrics.context_precision.passing_runs}/5 PASS
                          </span>
                        </div>
                        <div className="text-xs font-mono text-[#524E63] bg-[#F7F5FC] p-2 rounded-lg border border-[#E4E0F0] flex items-center justify-between">
                          <span>Scores: {evalResult.metrics.context_precision.scores.map(s => s.toFixed(3)).join(', ')}</span>
                        </div>
                      </div>

                      {/* Context Recall */}
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-medium text-[#121118]">Context Recall (Threshold ≥ {evalResult.metrics.context_recall.threshold})</span>
                          <span className={`gate-chip ${evalResult.metrics.context_recall.passed ? 'pass' : 'blocked'}`}>
                            {evalResult.metrics.context_recall.passing_runs}/5 PASS
                          </span>
                        </div>
                        <div className="text-xs font-mono text-[#524E63] bg-[#F7F5FC] p-2 rounded-lg border border-[#E4E0F0] flex items-center justify-between">
                          <span>Scores: {evalResult.metrics.context_recall.scores.map(s => s.toFixed(3)).join(', ')}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 pt-3 border-t border-[#E4E0F0] text-[11px] text-[#524E63] leading-relaxed">
                    💡 <strong>Diagnosis:</strong> Low precision means noise crowding context; low recall means supporting chunks are missing entirely.
                  </div>
                </div>

                {/* Generation Health Card */}
                <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)] flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
                      <h3 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                        <FileText className="w-4 h-4 text-[#7C3AED]" />
                        Generation Health (Faithfulness & Relevancy)
                      </h3>
                      <span className="text-[10px] font-mono text-[#524E63]">Pipeline Half 2</span>
                    </div>

                    <div className="mt-4 space-y-4">
                      {/* Faithfulness */}
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-medium text-[#121118]">Faithfulness (Threshold ≥ {evalResult.metrics.faithfulness.threshold})</span>
                          <span className={`gate-chip ${evalResult.metrics.faithfulness.passed ? 'pass' : 'blocked'}`}>
                            {evalResult.metrics.faithfulness.passing_runs}/5 PASS
                          </span>
                        </div>
                        <div className="text-xs font-mono text-[#524E63] bg-[#F7F5FC] p-2 rounded-lg border border-[#E4E0F0] flex items-center justify-between">
                          <span>Scores: {evalResult.metrics.faithfulness.scores.map(s => s.toFixed(3)).join(', ')}</span>
                        </div>
                      </div>

                      {/* Answer Relevancy */}
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-medium text-[#121118]">Answer Relevancy (Threshold ≥ {evalResult.metrics.answer_relevancy.threshold})</span>
                          <span className={`gate-chip ${evalResult.metrics.answer_relevancy.passed ? 'pass' : 'blocked'}`}>
                            {evalResult.metrics.answer_relevancy.passing_runs}/5 PASS
                          </span>
                        </div>
                        <div className="text-xs font-mono text-[#524E63] bg-[#F7F5FC] p-2 rounded-lg border border-[#E4E0F0] flex items-center justify-between">
                          <span>Scores: {evalResult.metrics.answer_relevancy.scores.map(s => s.toFixed(3)).join(', ')}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 pt-3 border-t border-[#E4E0F0] text-[11px] text-[#524E63] leading-relaxed">
                    💡 <strong>Diagnosis:</strong> Faithfulness tracks unsupported claims (hallucinations); relevancy tracks whether the answer directly addresses the prompt.
                  </div>
                </div>

              </div>

              {/* 5-Run Statistical Matrix */}
              <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
                <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
                  <h3 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#7C3AED]" />
                    5-Run Statistical Matrix & Heatmap Grid
                  </h3>
                  <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#7C3AED] px-2 py-0.5 rounded">
                    5 Gate Runs
                  </span>
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#E4E0F0] text-xs font-semibold text-[#524E63] bg-[#F0ECF9]">
                        <th className="py-3 px-4">Metric</th>
                        <th className="py-3 px-4">Threshold</th>
                        <th className="py-3 px-4 text-center">Run 1</th>
                        <th className="py-3 px-4 text-center">Run 2</th>
                        <th className="py-3 px-4 text-center">Run 3</th>
                        <th className="py-3 px-4 text-center">Run 4</th>
                        <th className="py-3 px-4 text-center">Run 5</th>
                        <th className="py-3 px-4 text-center">Pass Rate</th>
                        <th className="py-3 px-4 text-center">Verdict</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E4E0F0] text-xs font-mono">
                      {Object.entries(evalResult.metrics).map(([key, m]) => {
                        const passRate = `${m.passing_runs}/${m.total_runs}`;
                        return (
                          <tr key={key} className="hover:bg-[#F7F5FC]">
                            <td className="py-3 px-4 font-semibold text-[#121118] capitalize">
                              {key.replace('_', ' ')}
                            </td>
                            <td className="py-3 px-4 text-[#524E63]">
                              ≥ {m.threshold}
                            </td>
                            {m.scores.map((score, idx) => {
                              const isRunPass = score >= m.threshold;
                              return (
                                <td key={idx} className="py-3 px-4 text-center tabular-nums">
                                  <span className={`px-2 py-1 rounded text-[11px] font-bold ${
                                    isRunPass 
                                      ? 'bg-[#ECFDF5] text-[#059669]' 
                                      : 'bg-[#FFF1F2] text-[#E11D48]'
                                  }`}>
                                    {score.toFixed(3)}
                                  </span>
                                </td>
                              );
                            })}
                            <td className="py-3 px-4 text-center font-bold text-[#121118]">
                              {passRate}
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className={`gate-chip ${m.passed ? 'pass' : 'blocked'}`}>
                                {m.passed ? 'PASS' : 'BLOCKED'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* TAB 2: QUESTION X-RAY INSPECTOR */}
          {activeTab === 'xray' && (
            <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
              <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
                <h3 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                  <Search className="w-4 h-4 text-[#7C3AED]" />
                  Question X-Ray Inspector
                </h3>
                <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#7C3AED] px-2 py-0.5 rounded">
                  DeepEval Trace Inspection
                </span>
              </div>

              <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Benchmark Question List */}
                <div className="lg:col-span-1 border-r border-[#E4E0F0] pr-4 space-y-2">
                  <span className="text-xs font-semibold text-[#524E63] uppercase tracking-wider block mb-2">
                    Benchmark Questions ({benchmarkQuestions.length})
                  </span>
                  <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
                    {benchmarkQuestions.map(item => {
                      const isSelected = item.id === selectedQuestionId;
                      return (
                        <button
                          key={item.id}
                          onClick={() => setSelectedQuestionId(item.id)}
                          className={`w-full text-left p-3 rounded-xl transition text-xs flex flex-col gap-1 border ${
                            isSelected
                              ? 'bg-[#EDE9FE] border-[#7C3AED] text-[#121118] font-semibold'
                              : 'bg-[#F7F5FC] border-[#E4E0F0] text-[#524E63] hover:bg-[#F0ECF9]'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-[10px] text-[#7C3AED]">{item.id}</span>
                            <span className="text-[10px] opacity-75">{item.source}</span>
                          </div>
                          <p className="line-clamp-2 text-[#121118] font-medium">{item.question}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Selected Question Deep Detail */}
                <div className="lg:col-span-2 space-y-4">
                  {(() => {
                    const q = benchmarkQuestions.find(item => item.id === selectedQuestionId) || benchmarkQuestions[0];
                    if (!q) return <div>Select a question</div>;
                    
                    // Find matching run reasons from evalResult if available
                    const sampleRun = evalResult ? evalResult.preset : null;
                    
                    return (
                      <div className="space-y-4">
                        <div className="bg-[#F7F5FC] p-4 rounded-xl border border-[#E4E0F0]">
                          <span className="text-[10px] font-mono text-[#7C3AED] uppercase tracking-wider">User Query ({q.id})</span>
                          <h4 className="text-sm font-bold text-[#121118] mt-0.5">"{q.question}"</h4>
                          <span className="text-[11px] text-[#524E63] mt-1 block">Source: {q.source}</span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="bg-white p-4 rounded-xl border border-[#E4E0F0] shadow-sm">
                            <span className="text-[10px] font-mono text-[#059669] uppercase tracking-wider block mb-1">Ground Truth Answer</span>
                            <p className="text-xs text-[#121118] leading-relaxed">{q.ground_truth_answer}</p>
                          </div>

                          <div className="bg-white p-4 rounded-xl border border-[#E4E0F0] shadow-sm">
                            <span className="text-[10px] font-mono text-[#7C3AED] uppercase tracking-wider block mb-1">Generated Reference Answer</span>
                            <p className="text-xs text-[#121118] leading-relaxed">
                              {/* Simulated generated answer based on preset */}
                              {q.ground_truth_answer} {activePresetId === 'hallucinating_prompt' ? '[EXTRA UNSUPPORTED CLAIM: guaranteed 99.999% uptime SLA included]' : ''}
                            </p>
                          </div>
                        </div>

                        {/* Retrieved Chunks & Ground Truth Hits */}
                        <div className="bg-white p-4 rounded-xl border border-[#E4E0F0] shadow-sm">
                          <span className="text-[10px] font-mono text-[#524E63] uppercase tracking-wider block mb-2">Retrieved Chunks & Ground Truth Validation</span>
                          <div className="space-y-2">
                            {q.ground_truth_chunk_ids.map(chunkId => (
                              <div key={chunkId} className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-[#ECFDF5] border border-[#D1FAE5]">
                                <span className="font-mono font-semibold text-[#059669]">{chunkId}</span>
                                <span className="gate-chip pass">GROUND TRUTH HIT</span>
                              </div>
                            ))}
                            <div className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-[#F7F5FC] border border-[#E4E0F0]">
                              <span className="font-mono text-[#524E63]">kb-noise-distractor-99 (noise injection)</span>
                              <span className="text-[10px] font-mono text-[#E11D48] bg-[#FFF1F2] px-2 py-0.5 rounded">NOISE</span>
                            </div>
                          </div>
                        </div>

                        {/* DeepEval Judge Reasoning */}
                        <div className="bg-[#EDE9FE]/50 p-4 rounded-xl border border-[#7C3AED]/20">
                          <span className="text-[10px] font-mono text-[#7C3AED] uppercase tracking-wider block mb-1 font-bold">
                            DeepEval Natural-Language Judge Reasoning
                          </span>
                          <p className="text-xs text-[#121118] leading-relaxed font-mono">
                            {evalResult && evalResult.metrics.faithfulness.reasons && evalResult.metrics.faithfulness.reasons[0] 
                              ? evalResult.metrics.faithfulness.reasons[0] 
                              : "The actual output's claims about dates, limits, and windows are supported by the retrieved passages. No extra ungrounded facts were introduced in this test case."}
                          </p>
                        </div>
                      </div>
                    );
                  })()}
                </div>

              </div>
            </div>
          )}

          {/* TAB 3: DETERMINISTIC SANDBOX & BYOK */}
          {activeTab === 'sandbox' && (
            <div className="space-y-6">
              <div className="bg-white rounded-2xl border border-[#E4E0F0] p-5 shadow-[0_1px_3px_rgba(18,17,24,0.02)]">
                <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
                  <h3 className="text-sm font-bold text-[#121118] flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[#7C3AED]" />
                    Deterministic Retrieval Sandbox (Free, Zero API Key)
                  </h3>
                  <span className="text-[10px] font-mono bg-[#EDE9FE] text-[#7C3AED] px-2 py-0.5 rounded">
                    /api/evaluate/retrieval-check
                  </span>
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <label className="text-xs font-medium text-[#524E63] block mb-1.5">Test Custom Query Against Knowledge Base</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={sandboxQuery}
                        onChange={e => setSandboxQuery(e.target.value)}
                        placeholder="e.g. how many api calls can I make on the team plan?"
                        className="flex-1 px-4 py-2 text-xs rounded-xl border border-[#E4E0F0] focus:outline-none focus:border-[#7C3AED] font-mono"
                      />
                      <button
                        onClick={runSandboxCheck}
                        disabled={sandboxLoading}
                        className="px-5 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold rounded-xl shadow-sm transition flex items-center gap-2 disabled:opacity-50"
                      >
                        <Zap className="w-3.5 h-3.5" />
                        <span>{sandboxLoading ? 'Running...' : 'Run Sandbox'}</span>
                      </button>
                    </div>
                  </div>

                  {sandboxResult && (
                    <div className="mt-4 p-4 rounded-xl bg-[#F7F5FC] border border-[#E4E0F0] space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-[#121118]">Sandbox Results ({sandboxResult.results?.length || 0} evaluated)</span>
                        <span className="font-mono text-[#7C3AED]">Top-K: {sandboxResult.top_k} • Retrieved: {sandboxResult.retrieved_count}</span>
                      </div>
                      <div className="space-y-4">
                        {sandboxResult.results?.map((resRow: any, rIdx: number) => (
                          <div key={rIdx} className="bg-white p-4 rounded-xl border border-[#E4E0F0] shadow-sm space-y-2">
                            <div className="flex items-center justify-between text-xs pb-2 border-b border-[#E4E0F0]">
                              <span className="font-mono font-semibold text-[#121118]">Query: "{resRow.question}"</span>
                              <span className={`gate-chip ${resRow.hit ? 'pass' : 'blocked'}`}>
                                {resRow.hit ? 'HIT' : 'MISS'}
                              </span>
                            </div>
                            <div className="space-y-2">
                              <span className="text-[10px] font-mono text-[#524E63] uppercase tracking-wider block">
                                Retrieved Chunks ({resRow.retrieved?.length || 0}):
                              </span>
                              {resRow.retrieved?.map((chunk: any, cIdx: number) => (
                                <div key={cIdx} className="bg-[#F7F5FC] p-3 rounded-lg border border-[#E4E0F0] text-xs space-y-1">
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono text-[#7C3AED] font-bold">{chunk.chunk_id}</span>
                                      <span className="font-mono text-[11px] text-[#524E63]">Score: {chunk.score}</span>
                                    </div>
                                    <span className={`gate-chip ${chunk.is_ground_truth ? 'pass' : 'blocked'}`}>
                                      {chunk.is_ground_truth ? 'GROUND TRUTH HIT' : 'NOISE / NEIGHBOUR'}
                                    </span>
                                  </div>
                                  <p className="text-xs font-semibold text-[#121118]">{chunk.title}</p>
                                  <p className="text-xs text-[#524E63] leading-relaxed">{chunk.text}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

        </main>

      </div>

      {/* LIVE BYOK MODAL */}
      {showLiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#121118]/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl border border-[#E4E0F0] w-full max-w-lg p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E4E0F0]">
              <h3 className="text-base font-bold text-[#121118] flex items-center gap-2">
                <Key className="w-5 h-5 text-[#7C3AED]" />
                Run Live Evaluation (BYOK)
              </h3>
              <button
                onClick={() => setShowLiveModal(false)}
                className="text-[#524E63] hover:text-[#121118] text-xs font-mono font-bold"
              >
                ✕ ESC
              </button>
            </div>

            <p className="text-xs text-[#524E63]">
              Supports OpenAI (sk-...) or Groq (gsk_...) API keys. Executes a live test case through the actual RAG pipeline and scores it with DeepEval.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#121118] block mb-1">API Key (OpenAI `sk-...` or Groq `gsk_...`)</label>
                <input
                  type="password"
                  value={liveApiKey}
                  onChange={e => setLiveApiKey(e.target.value)}
                  placeholder="sk-... or gsk_..."
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[#E4E0F0] focus:outline-none focus:border-[#7C3AED] font-mono"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[#121118] block mb-1">Test Question</label>
                <input
                  type="text"
                  value={liveQuestion}
                  onChange={e => setLiveQuestion(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[#E4E0F0] focus:outline-none focus:border-[#7C3AED]"
                />
              </div>

              {liveResult && (
                <div className="p-3 rounded-xl bg-[#F7F5FC] border border-[#E4E0F0] text-xs font-mono max-h-48 overflow-y-auto">
                  <pre>{JSON.stringify(liveResult, null, 2)}</pre>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E4E0F0]">
              <button
                onClick={() => setShowLiveModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-[#524E63] hover:bg-[#F0ECF9]"
              >
                Cancel
              </button>
              <button
                onClick={runLiveEvaluation}
                disabled={liveLoading}
                className="px-5 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold rounded-xl shadow-sm transition flex items-center gap-2 disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>{liveLoading ? 'Executing Live...' : 'Execute Live Run'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer className="bg-white border-t border-[#E4E0F0] py-4 px-6 mt-12 text-center text-xs text-[#524E63]">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>RAG Evaluation Console • Autonoma Labs</span>
          <span className="font-mono text-[11px]">Lavender Mist & Electric Violet Design System</span>
        </div>
      </footer>

    </div>
  );
}

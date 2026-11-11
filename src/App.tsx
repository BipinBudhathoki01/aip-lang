import {useEffect, useMemo, useRef, useState} from 'react';
import {Button} from '@astryxdesign/core/Button';
import {ArrowUpRight, BookOpen, Braces, Check, ChevronRight, Code2, Copy, Download, FileCode2, Github, Play, Terminal} from 'lucide-react';
import {parseAipClient} from './parser/clientAipParser';
import {SAMPLES} from './samples';
import type {SystemPromptAST, UserPromptAST} from './types/aip';

const repository = 'https://github.com/BipinBudhathoki01/aip-lang';
const docs = 'https://bipinbudhathoki01.github.io/aip-lang/';
const local = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
const initial = SAMPLES[0];
const tabs = ['Schema', 'Prompt preview', 'AST', 'Output'] as const;
type Tab = typeof tabs[number];

export default function App() {
  const [code, setCode] = useState(initial.code.replaceAll('gemini-2.0-flash', 'gemini-3.8-flash'));
  const [sample, setSample] = useState(initial.id);
  const [variables, setVariables] = useState<Record<string, string>>({...initial.defaultVariables});
  const [tab, setTab] = useState<Tab>('Schema');
  const [output, setOutput] = useState('Run the current prompt with a local mock to inspect its rendered inputs and validated fixture output.');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current); }, []);
  const {ast, error} = useMemo(() => parseAipClient(code), [code]);
  const names = ast?.variables || [];
  const fields = Object.entries(ast?.generate?.schema || {});
  const lineCount = code.split('\n').length;

  function chooseSample(id: string) {
    const next = SAMPLES.find(item => item.id === id)!;
    setSample(id);
    setCode(next.code.replaceAll('gemini-2.0-flash', 'gemini-3.8-flash'));
    setVariables({...next.defaultVariables});
    setOutput('Example loaded. Run mock locally to inspect its current result.');
    setFailed(false);
  }

  async function execute(action: 'run' | 'parse') {
    setBusy(true); setTab('Output'); setFailed(false);
    try {
      const response = await fetch(action === 'run' ? '/api/run-runtime' : '/api/run-python', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, variables}),
        signal: AbortSignal.timeout(35_000),
      });
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Python execution needs the local server. Run npm run dev from the repository.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.output || 'Execution failed.');
      let formatted = data.output;
      try { formatted = JSON.stringify(JSON.parse(data.output), null, 2); } catch { /* retain diagnostics */ }
      setOutput(formatted);
    } catch (err) { setOutput(err instanceof Error ? err.message : String(err)); setFailed(true); }
    finally { setBusy(false); }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([code], {type: 'text/plain;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `${sample}.aiprompt`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(code); setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1800);
    } catch { setOutput('Clipboard is unavailable. Select and copy source from the editor.'); setTab('Output'); }
  }

  const rendered = (prompt: SystemPromptAST | UserPromptAST | null | undefined) => prompt?.tokens.map(token => token.type === 'variable' ? (variables[token.name!] ?? `{{ $${token.name} }}`) : token.text).join('') || '';

  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to workspace</a>
    <header className="topbar">
      <a className="brand" href={docs}><strong>AIP Lang</strong><span className="version">0.1 preview</span></a>
      <nav aria-label="Main navigation"><a href={docs}>Documentation</a><a href={repository + '/blob/main/ROADMAP.md'}>Roadmap</a><a href={repository}><Github size={16}/> GitHub <ArrowUpRight size={13}/></a></nav>
    </header>
    <div className="workspace-layout">
      <aside className="sidebar">
        <div className="sidebar-label">WORKSPACE</div>
        <a href="#main" className="sidebar-link selected"><Code2 size={17}/> Playground <span className="nav-dot"/></a>
        <a className="sidebar-link" href={docs + 'quickstart/'}><BookOpen size={17}/> Quick start <ArrowUpRight size={13}/></a>
        <a className="sidebar-link" href={docs + 'language/'}><Braces size={17}/> Language reference</a>
        <div className="sidebar-divider"/>
        <div className="sidebar-label">EXAMPLES</div>
        {SAMPLES.map(item => <button key={item.id} className={`example-link ${sample === item.id ? 'active' : ''}`} onClick={() => chooseSample(item.id)}><FileCode2 size={15}/><span>{item.id.replaceAll('-', ' ')}</span>{sample === item.id && <ChevronRight size={13}/>}</button>)}
        <div className="sidebar-note"><span className="small-mark">{'{ }'}</span><strong>A small language.<br/>A clear contract.</strong><p>Prompts and output types,<br/>versioned together.</p><a href={repository + '/blob/main/CONTRIBUTING.md'}>Help build AIP <ArrowUpRight size={13}/></a></div>
        <div className="sidebar-foot">Open source · MIT license</div>
      </aside>

      <main id="main" className="main">
        <div className="breadcrumb">Workspace <ChevronRight size={12}/> <span>Playground</span></div>
        <div className="page-heading"><div><div className="eyebrow">EXPLORE THE LANGUAGE</div><h1>A place to try your prompts.</h1><p>Write a contract. Inspect its structure. See exactly what goes in and comes out.</p></div><Button label="Read the guide" href={docs + 'quickstart/'} variant="secondary" icon={<BookOpen size={15}/>}/></div>
        <div className="environment-note"><span className={`status-dot ${local ? 'green' : ''}`}/><strong>{local ? 'Local workspace' : 'Browser workspace'}</strong><span>{local ? 'Mock runs use your local Python runtime. No model requests or API key needed.' : 'Preview source, variables, and schemas here. Python execution is available in the local app.'}</span></div>

        <div className="editor-grid">
          <section className="panel source-panel" aria-labelledby="source-heading">
            <div className="panel-heading"><div className="filename" id="source-heading"><FileCode2 size={16}/>{sample}.aiprompt<span className="file-tag">source</span></div><div className="panel-actions"><Button label={copied ? 'Copied' : 'Copy source'} variant="ghost" size="sm" isIconOnly icon={copied ? <Check size={15}/> : <Copy size={15}/>} onClick={copy}/><Button label="Download source" variant="ghost" size="sm" isIconOnly icon={<Download size={15}/>} onClick={download}/></div></div>
            <div className="code-area"><div className="line-numbers" aria-hidden="true">{Array.from({length: lineCount}, (_, i) => <span key={i}>{i + 1}</span>)}</div><textarea aria-label="AIP prompt source" value={code} onChange={event => setCode(event.target.value)} spellCheck={false} autoCapitalize="off" autoComplete="off" wrap="off" className="source-editor"/></div>
            <div className="editor-status"><span className={error ? 'error-text' : 'valid-text'}>{error ? 'Preview error' : <><Check size={13}/> Browser preview ready</>}</span><span>{lineCount} lines <span className="status-separator">·</span> UTF-8</span></div>
            <div className="run-toolbar"><span>Validate with the Python parser locally.</span><div><Button label="Parse with Python" variant="secondary" size="sm" isDisabled={!local || busy} onClick={() => execute('parse')}/><Button label="Run mock" variant="primary" size="sm" isDisabled={!local || busy} isLoading={busy} icon={<Play size={13}/>} onClick={() => execute('run')}/></div></div>
          </section>

          <section className="panel inspector" aria-label="Prompt inspector">
            <div className="inspector-tabs" role="tablist" aria-label="Inspector views">{tabs.map((name, i) => <button key={name} role="tab" id={`tab-${i}`} aria-controls="inspector-content" aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const index = (i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length; setTab(tabs[index]); document.getElementById(`tab-${index}`)?.focus(); } }} className={tab === name ? 'current' : ''} onClick={() => setTab(name)}>{name}</button>)}</div>
            <div id="inspector-content" role="tabpanel" aria-labelledby={`tab-${tabs.indexOf(tab)}`} className="inspector-content" tabIndex={0}>
              {error && <div role="alert" className="error-banner">{error}</div>}
              {tab === 'Schema' && <><div className="section-kicker">OUTPUT CONTRACT</div><h2>{ast?.generate?.target_class || 'Untitled result'}</h2><p className="muted">Required fields returned by the generation step.</p><div className="field-table"><div className="field-row table-head"><span>FIELD</span><span>TYPE</span></div>{fields.map(([name, type]) => <div className="field-row" key={name}><span><span className="field-dot"/>{name}</span><code>{type.kind === 'object' ? 'object' : type.repr || type.name}</code></div>)}{!fields.length && <p className="empty-state">Add a schema inside a generate block to inspect fields.</p>}</div><div className="schema-heading"><Braces size={14}/><span>JSON Schema</span></div><pre className="json-code">{JSON.stringify(ast?.generate?.json_schema || {}, null, 2)}</pre></>}
              {tab === 'Prompt preview' && <><div className="section-kicker">RENDERED INPUT</div><h2>What the model receives</h2><p className="muted">Values below come from your current variables.</p><h3>System instruction</h3><pre className="prompt-preview">{rendered(ast?.system_prompt) || 'No system instruction.'}</pre><h3>User prompt</h3><pre className="prompt-preview">{rendered(ast?.user_prompt) || 'No user prompt.'}</pre></>}
              {tab === 'AST' && <><div className="section-kicker">BROWSER PARSER</div><h2>Abstract syntax tree</h2><p className="muted">A preview of sections, tokens, and type declarations. Python remains authoritative.</p><pre className="json-code">{JSON.stringify(ast, null, 2)}</pre></>}
              {tab === 'Output' && <><div className="section-kicker">LOCAL EXECUTION</div><h2>Run output</h2><p className="muted">Mock fixtures test integration. They are not AI answers.</p><pre aria-live="polite" role={failed ? 'alert' : 'status'} className={`json-code ${failed ? 'error-text' : ''}`}>{busy ? 'Running the current source…' : output}</pre>{!local && <div className="local-instructions"><Terminal size={18}/><div><strong>Run Python on your machine</strong><p>Clone the repo, install Python dependencies, then run:</p><code>npm ci &amp;&amp; npm run dev</code><a href={docs + 'quickstart/'}>Full setup instructions <ArrowUpRight size={12}/></a></div></div>}</>}
            </div>
          </section>
        </div>

        <section className="panel variables-panel" aria-labelledby="variables-heading"><div className="panel-heading"><div className="filename" id="variables-heading"><Braces size={16}/> Template variables <span className="count-badge">{names.length}</span></div><span className="muted small">Used in the prompt preview and local runs</span></div><div className="variables-grid">{names.map(name => <label key={name} className="variable-field"><span><code>${name}</code><span>string</span></span><textarea rows={name === 'text' || name === 'message' ? 3 : 2} value={variables[name] ?? ''} onChange={event => setVariables(previous => ({...previous, [name]: event.target.value}))}/></label>)}{!names.length && <p className="muted">Add a variable such as {'{{ $message }}'} to your prompt.</p>}</div></section>
        <footer className="workspace-footer"><span><span className="status-dot green"/> Your source stays in this browser until you run it locally.</span><a href="https://github.com/meta/astryx">UI built with Astryx <ArrowUpRight size={12}/></a></footer>
      </main>
    </div>
  </div>;
}

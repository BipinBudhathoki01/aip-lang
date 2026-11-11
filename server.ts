import 'dotenv/config';
import express, { Request, Response } from 'express';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const root = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const localPython = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.PYTHON_BIN || (fs.existsSync(localPython) ? localPython : (process.platform === 'win32' ? 'python' : 'python3'));
app.use(express.json({ limit: '100kb' }));

function runPython(res: Response, args: string[], input?: unknown) {
  const started = Date.now();
  const child = spawn(python, args, { cwd: root, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  let output = '';
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; child.kill(); }, 30_000);
  child.stdout.on('data', chunk => { output += chunk.toString(); });
  child.stderr.on('data', chunk => { output += chunk.toString(); });
  child.stdin.on('error', () => {});
  child.on('error', () => {
    clearTimeout(timer);
    if (!res.headersSent) res.status(500).json({ output: 'Python could not start. Install dependencies or set PYTHON_BIN.', exitCode: 1 });
  });
  child.on('close', exitCode => {
    clearTimeout(timer);
    if (!res.headersSent) res.status(exitCode === 0 ? 200 : 400).json({ output: timedOut ? 'Execution timed out.' : output, exitCode: exitCode ?? 1, durationMs: Date.now() - started });
  });
  child.stdin.end(input === undefined ? undefined : JSON.stringify(input));
}

for (const [endpoint, action] of [['/api/run-python', 'parse'], ['/api/run-runtime', 'run']] as const) {
  app.post(endpoint, (req: Request, res: Response) => {
    if (typeof req.body?.code !== 'string') return res.status(400).json({ output: 'Editor source is required.', exitCode: 1 });
    const variables = req.body.variables ?? {};
    if (typeof variables !== 'object' || variables === null || Array.isArray(variables)) return res.status(400).json({ output: 'Variables must be a JSON object.', exitCode: 1 });
    runPython(res, ['playground_runner.py'], { code: req.body.code, variables, action });
  });
}
app.post('/api/run-tests', (_req, res) => runPython(res, ['-m', 'unittest', 'discover', '-s', 'tests', '-v']));

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer } = await import('vite');
    app.use((await createServer({ server: { middlewareMode: true }, appType: 'spa' })).middlewares);
  } else {
    app.use(express.static(path.join(root, 'dist')));
    app.get('*', (_req, res) => res.sendFile(path.join(root, 'dist/index.html')));
  }
  const port = Number(process.env.PORT || 3000);
  app.listen(port, '127.0.0.1', () => console.log(`AIP playground: http://127.0.0.1:${port}`));
}
startServer().catch(error => { console.error(error); process.exitCode = 1; });

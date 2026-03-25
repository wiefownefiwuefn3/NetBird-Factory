import json
import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# ----------------------------------------------------------------------
# Data directory & Thread-Safe Locking
# ----------------------------------------------------------------------
DATA_DIR = os.environ.get('WEBAPP_DATA', 'webapp_data')
os.makedirs(DATA_DIR, exist_ok=True)

TASKS_FILE = os.path.join(DATA_DIR, 'tasks.json')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')
WORKERS_FILE = os.path.join(DATA_DIR, 'workers.json')

db_lock = threading.Lock()

def initialize_files():
    with db_lock:
        for f in[TASKS_FILE, RESULTS_FILE, WORKERS_FILE]:
            if not os.path.exists(f) or os.path.getsize(f) == 0:
                with open(f, 'w') as fp:
                    json.dump([], fp)

initialize_files()

# ----------------------------------------------------------------------
# HTML Template
# ----------------------------------------------------------------------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fleet Command Console</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Fira Code', 'monospace'] },
                    colors: { zinc: { 950: '#09090b' } }
                }
            }
        }
    </script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { background-color: #09090b; color: #e4e4e7; }
        .custom-scroll::-webkit-scrollbar { width: 4px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 10px; }
        .node-card.selected { border-color: #10b981; background: rgba(16, 185, 129, 0.05); }
        .terminal-line:hover { background: rgba(255,255,255,0.03); }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden font-sans">

    <!-- Header -->
    <header class="h-14 border-b border-zinc-800 flex items-center justify-between px-6 bg-zinc-900/50">
        <div class="flex items-center gap-3">
            <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <h1 class="text-sm font-bold tracking-widest uppercase text-zinc-400">Fleet Command <span class="text-zinc-600 font-normal ml-2">v2.1</span></h1>
        </div>
        <div class="flex items-center gap-6">
            <div class="text-[11px] font-mono text-zinc-500"><span id="active-count">0</span> NODES ACTIVE</div>
            <div class="h-4 w-px bg-zinc-800"></div>
            <div class="text-[11px] font-mono text-zinc-500">POLLING: 3S</div>
        </div>
    </header>

    <div class="flex flex-1 overflow-hidden">
        
        <!-- Left Pane: The Fleet -->
        <aside class="w-72 border-r border-zinc-800 flex flex-col bg-zinc-950">
            <div class="p-4 border-b border-zinc-800">
                <h2 class="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-3">Live Agents (5m window)</h2>
                <button id="broadcastBtn" onclick="selectTarget('all')" class="w-full py-2 px-3 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold flex items-center justify-center gap-2 transition-all">
                    <i data-lucide="radio" class="w-3.5 h-3.5"></i> Broadcast to All
                </button>
            </div>
            <div id="workersList" class="flex-1 overflow-y-auto custom-scroll p-2 space-y-1">
                <!-- Workers go here -->
                <div class="p-4 text-center text-xs text-zinc-600 italic">Searching for agents...</div>
            </div>
        </aside>

        <!-- Center Pane: Command & Execution -->
        <main class="flex-1 flex flex-col bg-zinc-900/20">
            <div class="p-8 max-w-4xl mx-auto w-full flex-1 flex flex-col">
                
                <!-- Target Indicator -->
                <div class="mb-6 flex items-center gap-3">
                    <span class="text-xs font-medium text-zinc-500">Targeting:</span>
                    <span id="targetBadge" class="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-xs font-bold border border-emerald-500/20 shadow-sm">
                        ALL_BROADCAST
                    </span>
                </div>

                <!-- Input Box -->
                <div class="relative group mb-8">
                    <div class="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 rounded-xl blur opacity-25 group-focus-within:opacity-100 transition duration-1000"></div>
                    <div class="relative flex items-center bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden focus-within:border-zinc-500 transition-all">
                        <div class="pl-4 text-zinc-500 font-mono italic select-none">$</div>
                        <input type="text" id="commandInput" placeholder="Enter shell command..." 
                            class="w-full bg-transparent px-4 py-5 text-zinc-100 font-mono focus:outline-none">
                        <button id="sendBtn" class="mr-3 bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 rounded-lg font-bold text-sm transition-all flex items-center gap-2">
                            Deploy <i data-lucide="send" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>

                <!-- History -->
                <div class="mb-8">
                    <h3 class="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <i data-lucide="history" class="w-3 h-3"></i> Quick Redploy
                    </h3>
                    <div id="commandHistory" class="flex flex-wrap gap-2">
                        <!-- History items -->
                    </div>
                </div>

                <!-- Pending Tasks -->
                <div class="flex-1 min-h-0 flex flex-col">
                    <h3 class="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-3">Deployment Queue</h3>
                    <div id="tasksList" class="bg-zinc-950/50 border border-zinc-800 rounded-lg p-4 font-mono text-xs text-zinc-500 overflow-y-auto custom-scroll">
                        No pending tasks in queue.
                    </div>
                </div>
            </div>
        </main>

        <!-- Right Pane: Telemetry -->
        <aside class="w-96 border-l border-zinc-800 bg-zinc-950 flex flex-col">
            <div class="p-4 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/30">
                <h2 class="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Telemetry Feed</h2>
                <button onclick="document.getElementById('resultsList').innerHTML=''" class="text-zinc-600 hover:text-zinc-400">
                    <i data-lucide="eraser" class="w-3.5 h-3.5"></i>
                </button>
            </div>
            <div id="resultsList" class="flex-1 overflow-y-auto custom-scroll p-4 font-mono text-[11px] space-y-4">
                <div class="text-zinc-700 italic">Waiting for incoming data...</div>
            </div>
        </aside>

    </div>

    <!-- Toast Container -->
    <div id="toast-container" class="fixed bottom-6 right-6 z-50 flex flex-col gap-2"></div>

    <script>
        lucide.createIcons();
        let selectedTarget = 'all';
        let commandHistory = [];

        const escapeHTML = (str) => {
            if (!str) return '';
            return str.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        };

        const showToast = (msg) => {
            const container = document.getElementById('toast-container');
            const div = document.createElement('div');
            div.className = "bg-zinc-800 border border-zinc-700 text-zinc-200 px-4 py-3 rounded-lg shadow-xl text-xs font-medium animate-bounce";
            div.innerText = msg;
            container.appendChild(div);
            setTimeout(() => div.remove(), 3000);
        };

        const selectTarget = (target) => {
            selectedTarget = target;
            const badge = document.getElementById('targetBadge');
            badge.innerText = target === 'all' ? 'ALL_BROADCAST' : target;
            badge.className = target === 'all' 
                ? "px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-xs font-bold border border-emerald-500/20"
                : "px-3 py-1 rounded-full bg-blue-500/10 text-blue-500 text-xs font-bold border border-blue-500/20";
            updateData();
        };

        async function updateData() {
            try {
                const [tasksRes, resultsRes, workersRes] = await Promise.all([
                    fetch('/api/tasks'), fetch('/api/results'), fetch('/api/workers')
                ]);
                const tasks = await tasksRes.json();
                const results = await resultsRes.json();
                const workers = await workersRes.json();

                // Logic: Remove agents older than 5 minutes (300,000 ms)
                const now = new Date().getTime();
                const activeWorkers = workers.filter(w => {
                    const lastSeen = new Date(w.lastSeen).getTime();
                    return (now - lastSeen) < 300000; 
                });

                document.getElementById('active-count').innerText = activeWorkers.length;

                // Update Workers List
                const wList = document.getElementById('workersList');
                if (activeWorkers.length === 0) {
                    wList.innerHTML = '<div class="p-4 text-center text-[10px] text-zinc-600 italic">No active agents online.</div>';
                } else {
                    wList.innerHTML = activeWorkers.map(w => `
                        <div onclick="selectTarget('${w.ip}')" class="node-card group p-3 rounded-lg border border-zinc-800 hover:border-zinc-600 cursor-pointer transition-all ${selectedTarget === w.ip ? 'selected' : ''}">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-bold truncate ${selectedTarget === w.ip ? 'text-emerald-400' : 'text-zinc-300'}">${escapeHTML(w.hostname || w.ip)}</span>
                                <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
                            </div>
                            <div class="mt-1 flex justify-between items-center">
                                <span class="text-[10px] text-zinc-600 font-mono">${w.ip}</span>
                                <span class="text-[9px] text-zinc-500 uppercase">${escapeHTML(w.os || 'Linux')}</span>
                            </div>
                        </div>
                    `).join('');
                }

                // Update Tasks Queue
                const tList = document.getElementById('tasksList');
                tList.innerHTML = tasks.length === 0 
                    ? 'No pending tasks in queue.' 
                    : tasks.map(t => `<div class="mb-1 border-b border-zinc-900 pb-1 text-zinc-400"><span class="text-emerald-700">#${t.id}</span> ${escapeHTML(t.command)} <span class="text-zinc-700">[Target: ${t.target}]</span></div>`).join('');

                // Update Telemetry (Right Pane)
                const rList = document.getElementById('resultsList');
                if (results.length > 0) {
                    rList.innerHTML = results.slice(-20).reverse().map(r => `
                        <div class="terminal-line border-l border-zinc-800 pl-3 py-1">
                            <div class="text-[9px] text-zinc-600 mb-1 flex justify-between">
                                <span>FROM: ${escapeHTML(r.worker || r.ip)}</span>
                                <span>TASK: ${r.id}</span>
                            </div>
                            <div class="text-zinc-300 break-words whitespace-pre-wrap">${escapeHTML(r.output || r.result)}</div>
                        </div>
                    `).join('');
                }

                lucide.createIcons();
            } catch (err) { console.error("Update error", err); }
        }

        const execute = async () => {
            const cmdInput = document.getElementById('commandInput');
            const cmd = cmdInput.value.trim();
            if(!cmd) return;

            const res = await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd, target: selectedTarget})
            });

            if(res.ok) {
                showToast(`Task deployed to ${selectedTarget}`);
                if (!commandHistory.includes(cmd)) {
                    commandHistory.unshift(cmd);
                    if(commandHistory.length > 6) commandHistory.pop();
                    renderHistory();
                }
                cmdInput.value = '';
                updateData();
            }
        };

        const renderHistory = () => {
            document.getElementById('commandHistory').innerHTML = commandHistory.map(c => `
                <button onclick="document.getElementById('commandInput').value='${escapeHTML(c)}'" 
                    class="px-3 py-1.5 rounded-md bg-zinc-800/50 border border-zinc-700 text-[11px] text-zinc-400 hover:text-white hover:border-zinc-500 transition-all font-mono">
                    ${escapeHTML(c)}
                </button>
            `).join('');
        };

        document.getElementById('sendBtn').onclick = execute;
        document.getElementById('commandInput').onkeypress = (e) => { if(e.key === 'Enter') execute(); };

        setInterval(updateData, 3000);
        updateData();
    </script>
</body>
</html>
'''

# ----------------------------------------------------------------------
# Flask App Backend
# ----------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    with db_lock, open(TASKS_FILE, 'r') as f:
        return jsonify(json.load(f))

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json
    if not data or 'command' not in data:
        return 'Missing command', 400
    with db_lock, open(TASKS_FILE, 'r+') as f:
        tasks = json.load(f)
        tasks.append({'id': len(tasks) + 1, 'command': data['command']})
        f.seek(0)
        json.dump(tasks, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/tasks/pop', methods=['GET'])
def pop_task():
    with db_lock, open(TASKS_FILE, 'r+') as f:
        tasks = json.load(f)
        if tasks:
            task = tasks.pop(0)
            f.seek(0)
            json.dump(tasks, f, indent=2)
            f.truncate()
            return jsonify(task)
        return '', 204

@app.route('/api/results', methods=['POST'])
def add_result():
    with db_lock, open(RESULTS_FILE, 'r+') as f:
        results = json.load(f)
        results.append(request.json)
        f.seek(0)
        json.dump(results, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/results', methods=['GET'])
def get_results():
    with db_lock, open(RESULTS_FILE, 'r') as f:
        return jsonify(json.load(f))

@app.route('/api/workers', methods=['POST'])
def register_worker():
    data = request.json
    if not data:
        return 'Missing data', 400
        
    # FIX: Added 'Z' to properly establish this timestamp as UTC on the server side
    data['lastSeen'] = datetime.utcnow().isoformat() + "Z"
    
    with db_lock, open(WORKERS_FILE, 'r+') as f:
        workers = json.load(f)
        existing = next((w for w in workers if w.get('ip') == data.get('ip')), None)
        if existing:
            existing.update(data)
        else:
            workers.append(data)
        f.seek(0)
        json.dump(workers, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/workers', methods=['GET'])
def get_workers():
    with db_lock, open(WORKERS_FILE, 'r') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    print("Dashboard started on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)

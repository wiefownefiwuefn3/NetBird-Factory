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
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetBird | Fleet Command</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        gray: { 850: '#181c25', 900: '#11141b', 950: '#0a0d12' },
                        emerald: { 400: '#34d399', 500: '#10b981', 600: '#059669' }
                    },
                    fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Fira Code', 'monospace'] }
                }
            }
        }
    </script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { background-color: #0a0d12; scrollbar-gutter: stable; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #0f1219; }
        ::-webkit-scrollbar-thumb { background: #374151; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: #10b981; }
        
        .terminal-bg { background: radial-gradient(circle at top left, #111827, #030712); }
        .node-card { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
        .node-card.active-target { border-color: #10b981; box-shadow: 0 0 15px rgba(16, 185, 129, 0.15); background: #111827; }
        .glow-text { text-shadow: 0 0 10px rgba(16, 185, 129, 0.5); }
        
        @keyframes pulse-border {
            0% { border-color: rgba(16, 185, 129, 0.2); }
            50% { border-color: rgba(16, 185, 129, 0.6); }
            100% { border-color: rgba(16, 185, 129, 0.2); }
        }
        .pulse-emerald { animation: pulse-border 2s infinite; }
    </style>
</head>
<body class="text-gray-300 font-sans h-screen overflow-hidden flex flex-col">

    <!-- Toast Notifications -->
    <div id="toast-container" class="fixed top-6 right-6 z-50 flex flex-col gap-3"></div>

    <!-- Top Navigation Bar -->
    <nav class="h-16 border-b border-gray-800 bg-gray-900/50 backdrop-blur-md flex items-center justify-between px-6 shrink-0">
        <div class="flex items-center gap-4">
            <div class="flex items-center gap-2">
                <div class="bg-emerald-500 p-1.5 rounded-lg shadow-[0_0_15px_rgba(16,185,129,0.4)]">
                    <i data-lucide="shield-check" class="w-5 h-5 text-gray-950"></i>
                </div>
                <span class="font-bold text-xl tracking-tight text-white">NETBIRD <span class="text-emerald-500 font-light">FLEET</span></span>
            </div>
            <div class="h-6 w-px bg-gray-800 mx-2"></div>
            <div class="flex gap-6 text-[11px] font-mono uppercase tracking-widest text-gray-500">
                <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span>System: <span class="text-emerald-400">Operational</span></span>
                </div>
                <div class="flex items-center gap-2">
                    <i data-lucide="cpu" class="w-3 h-3"></i>
                    <span>Nodes: <span id="stat-total" class="text-white">0</span></span>
                </div>
            </div>
        </div>
        
        <div class="flex items-center gap-3">
            <div id="connection-timer" class="text-[11px] font-mono text-gray-500 border border-gray-800 px-3 py-1 rounded-full bg-black/20">
                POLLING: 3.0s
            </div>
        </div>
    </nav>

    <main class="flex flex-1 overflow-hidden">
        <!-- Sidebar: Node Management -->
        <aside class="w-80 border-r border-gray-800 bg-gray-900/30 flex flex-col">
            <div class="p-4 border-b border-gray-800">
                <div class="relative group">
                    <i data-lucide="search" class="w-4 h-4 absolute left-3 top-3 text-gray-600 group-focus-within:text-emerald-500 transition-colors"></i>
                    <input type="text" id="nodeSearch" placeholder="Filter nodes..." 
                        class="w-full bg-gray-950 border border-gray-800 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-emerald-500 transition-all">
                </div>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4 space-y-3" id="workersList">
                <!-- Nodes populated by JS -->
                <div class="flex items-center justify-center h-20 text-gray-600 text-sm italic">
                    Initializing node discovery...
                </div>
            </div>

            <div class="p-4 bg-gray-900/50 border-t border-gray-800">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Active Target</span>
                    <button id="resetTarget" class="text-[10px] text-emerald-500 hover:text-emerald-400 font-mono">RESET</button>
                </div>
                <div class="bg-gray-950 border border-emerald-500/30 rounded-md p-2 flex items-center gap-2">
                    <i data-lucide="target" class="w-4 h-4 text-emerald-500"></i>
                    <span id="currentTarget" class="font-mono text-sm text-emerald-400">all_broadcast</span>
                </div>
            </div>
        </aside>

        <!-- Main Content: Terminal & Execution -->
        <section class="flex-1 flex flex-col min-w-0 bg-gray-950">
            <!-- Command Input Area -->
            <div class="p-6 pb-0">
                <div class="relative flex items-center">
                    <div class="absolute left-4 text-emerald-500 font-mono font-bold select-none">#</div>
                    <input type="text" id="commandInput" placeholder="Enter shell command or payload..." 
                        class="w-full bg-gray-900 border border-gray-800 rounded-xl pl-10 pr-32 py-4 text-gray-100 font-mono shadow-2xl focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all">
                    <button id="sendBtn" class="absolute right-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2 rounded-lg font-bold transition-all flex items-center gap-2 group">
                        <span>EXECUTE</span>
                        <i data-lucide="zap" class="w-4 h-4 group-hover:scale-125 transition-transform"></i>
                    </button>
                </div>
                
                <!-- Command Chips -->
                <div id="commandHistory" class="flex gap-2 mt-3 overflow-x-auto pb-2">
                    <!-- History Chips populated by JS -->
                </div>
            </div>

            <!-- Terminal Window -->
            <div class="flex-1 flex flex-col p-6 pt-4 min-h-0">
                <div class="flex-1 terminal-bg border border-gray-800 rounded-xl overflow-hidden flex flex-col shadow-inner">
                    <!-- Terminal Header -->
                    <div class="bg-gray-900/80 px-4 py-2 border-b border-gray-800 flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <div class="flex gap-1.5">
                                <div class="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/40"></div>
                                <div class="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/40"></div>
                                <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/40"></div>
                            </div>
                            <span class="ml-2 text-[11px] font-mono text-gray-500 uppercase tracking-widest">Live Output Telemetry</span>
                        </div>
                        <div class="flex items-center gap-4">
                            <button onclick="document.getElementById('resultsList').innerHTML=''" class="text-gray-500 hover:text-white transition-colors">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Output Area -->
                    <div id="resultsList" class="flex-1 overflow-y-auto p-6 font-mono text-sm space-y-4 scroll-smooth">
                        <div class="text-gray-600 italic">No output received. Awaiting payload execution...</div>
                    </div>
                </div>

                <!-- Pending Queue -->
                <div class="mt-4 bg-gray-900/30 border border-gray-800 rounded-lg p-3">
                    <div class="flex items-center gap-2 mb-2">
                        <i data-lucide="layers" class="w-3 h-3 text-gray-500"></i>
                        <span class="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Pending Task Queue</span>
                    </div>
                    <div id="tasksList" class="flex gap-3 overflow-x-auto pb-1">
                        <span class="text-xs text-gray-700 italic">Queue clear.</span>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <script>
        lucide.createIcons();
        let selectedTarget = 'all';
        let history = [];
        let workerSearchTerm = '';

        const escapeHTML = (str) => {
            if (!str) return '';
            return str.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        };

        const timeAgo = (dateStr) => {
            const now = new Date();
            const then = new Date(dateStr).getTime();
            const seconds = Math.floor((now.getTime() - then) / 1000);
            if (seconds < 60) return "just now";
            if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
            return Math.floor(seconds / 3600) + "h ago";
        };

        const showToast = (message, type = 'success') => {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const colorClass = type === 'success' ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400';
            toast.className = `px-4 py-3 bg-gray-900 border-l-4 shadow-2xl rounded-r-lg font-mono text-xs flex items-center gap-3 animate-slide-in transition-all duration-300 translate-x-full`;
            toast.innerHTML = `<i data-lucide="${type === 'success' ? 'check-circle' : 'alert-triangle'}" class="w-4 h-4"></i> ${message}`;
            container.appendChild(toast);
            lucide.createIcons();
            setTimeout(() => { toast.classList.remove('translate-x-full'); }, 10);
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-x-full');
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        };

        async function updateData() {
            try {
                const [tasksRes, resultsRes, workersRes] = await Promise.all([
                    fetch('/api/tasks'), fetch('/api/results'), fetch('/api/workers')
                ]);
                const tasks = await tasksRes.json();
                const results = await resultsRes.json();
                const workers = await workersRes.json();

                // Stats
                document.getElementById('stat-total').innerText = workers.length;

                // Tasks
                const tasksContainer = document.getElementById('tasksList');
                if (tasks.length === 0) {
                    tasksContainer.innerHTML = '<span class="text-xs text-gray-700 italic">Queue clear.</span>';
                } else {
                    tasksContainer.innerHTML = tasks.map(t => `
                        <div class="bg-gray-800 border border-gray-700 px-3 py-1 rounded-full flex items-center gap-2 shrink-0">
                            <span class="text-[10px] text-emerald-500 font-bold">#${t.id}</span>
                            <span class="text-xs text-gray-300 font-mono">${escapeHTML(t.command.substring(0,20))}${t.command.length > 20 ? '...' : ''}</span>
                        </div>
                    `).join('');
                }

                // Results (Terminal)
                const resultsContainer = document.getElementById('resultsList');
                const wasScrolled = resultsContainer.scrollHeight - resultsContainer.clientHeight <= resultsContainer.scrollTop + 50;
                
                if (results.length > 0) {
                    resultsContainer.innerHTML = results.map(r => {
                        const output = r.output || r.result || JSON.stringify(r);
                        return `
                        <div class="group border-b border-gray-800/50 pb-4 last:border-0">
                            <div class="flex items-center gap-3 mb-2">
                                <span class="bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded text-[10px] font-bold border border-emerald-500/20">NODE: ${escapeHTML(r.worker || r.ip || 'unknown')}</span>
                                <span class="text-gray-600 text-[10px] font-mono">Task ID: ${r.id || 'N/A'}</span>
                            </div>
                            <pre class="text-gray-400 overflow-x-auto whitespace-pre-wrap leading-relaxed">${escapeHTML(output)}</pre>
                        </div>
                    `}).reverse().join('');
                }

                if (wasScrolled) resultsContainer.scrollTop = resultsContainer.scrollHeight;

                // Workers
                const workersContainer = document.getElementById('workersList');
                const filteredWorkers = workers.filter(w => 
                    (w.hostname || w.ip || '').toLowerCase().includes(workerSearchTerm.toLowerCase())
                );

                if (filteredWorkers.length === 0) {
                    workersContainer.innerHTML = `<div class="text-center py-10 text-gray-600 text-xs">No nodes matching "${workerSearchTerm}"</div>`;
                } else {
                    workersContainer.innerHTML = filteredWorkers.map(w => {
                        const isOnline = ((new Date().getTime() - new Date(w.lastSeen).getTime()) / 60000) < 5;
                        const isSelected = selectedTarget === w.ip;
                        return `
                        <div onclick="selectWorker('${w.ip}')" class="node-card p-3 rounded-xl border border-gray-800 cursor-pointer hover:border-gray-600 ${isSelected ? 'active-target border-emerald-500' : 'bg-gray-900/20'}">
                            <div class="flex justify-between items-start">
                                <div class="flex items-center gap-2">
                                    <i data-lucide="server" class="w-4 h-4 ${isOnline ? 'text-emerald-500' : 'text-gray-600'}"></i>
                                    <span class="text-sm font-semibold text-gray-200">${escapeHTML(w.hostname || 'Unknown Node')}</span>
                                </div>
                                <span class="w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-red-500'}"></span>
                            </div>
                            <div class="mt-2 flex justify-between items-end">
                                <div class="text-[10px] font-mono text-gray-500">
                                    <div>IP: ${escapeHTML(w.ip)}</div>
                                    <div class="uppercase">${escapeHTML(w.os || 'Linux')}</div>
                                </div>
                                <div class="text-[9px] text-gray-600 font-mono">${timeAgo(w.lastSeen)}</div>
                            </div>
                        </div>
                    `}).join('');
                    lucide.createIcons();
                }

            } catch (err) { console.error("Poll Error:", err); }
        }

        window.selectWorker = (ip) => {
            selectedTarget = ip;
            document.getElementById('currentTarget').innerText = ip;
            updateData();
        };

        document.getElementById('nodeSearch').addEventListener('input', (e) => {
            workerSearchTerm = e.target.value;
            updateData();
        });

        document.getElementById('resetTarget').onclick = () => {
            selectedTarget = 'all';
            document.getElementById('currentTarget').innerText = 'all_broadcast';
            updateData();
        };

        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');

        const executeCommand = async () => {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;
            
            sendBtn.disabled = true;
            sendBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i>`;
            lucide.createIcons();

            try {
                const res = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd, target: selectedTarget})
                });

                if(res.ok) {
                    showToast(`Payload deployed to ${selectedTarget}`, 'success');
                    if (!history.includes(cmd)) {
                        history.unshift(cmd);
                        if (history.length > 5) history.pop();
                        renderHistory();
                    }
                    cmdInput.value = '';
                } else {
                    showToast('Execution failed', 'error');
                }
            } catch (e) { showToast('Network unreachable', 'error'); }

            sendBtn.disabled = false;
            sendBtn.innerHTML = `<span>EXECUTE</span><i data-lucide="zap" class="w-4 h-4"></i>`;
            lucide.createIcons();
            updateData();
        };

        const renderHistory = () => {
            const container = document.getElementById('commandHistory');
            container.innerHTML = history.map(c => `
                <button onclick="document.getElementById('commandInput').value='${escapeHTML(c)}'" 
                    class="bg-gray-900 border border-gray-800 hover:border-emerald-500/50 px-3 py-1 rounded text-[10px] font-mono text-gray-500 whitespace-nowrap transition-colors">
                    ${escapeHTML(c)}
                </button>
            `).join('');
        };

        sendBtn.onclick = executeCommand;
        cmdInput.onkeypress = (e) => { if (e.key === 'Enter') executeCommand(); };

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

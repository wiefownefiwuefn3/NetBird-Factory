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
        for f in [TASKS_FILE, RESULTS_FILE, WORKERS_FILE]:
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
    <title>NetBird Fleet Command</title>
    
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🛸</text></svg>">
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        const origWarn = console.warn;
        console.warn = function(...args) {
            if (typeof args[0] === 'string' && args[0].includes('cdn.tailwindcss.com')) return;
            origWarn.apply(console, args);
        };

        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        gray: { 850: '#1f2937', 900: '#111827', 950: '#030712' },
                        emerald: { 400: '#34d399', 500: '#10b981', 600: '#059669' }
                    },
                    fontFamily: {
                        sans:['Inter', 'system-ui', 'sans-serif'],
                        mono:['Fira Code', 'ui-monospace', 'monospace']
                    }
                }
            }
        }
    </script>
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #4b5563; }
        .glass-panel { background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(55, 65, 81, 0.5); }
    </style>
</head>
<body class="bg-gray-950 text-gray-200 font-sans min-h-screen flex flex-col p-4 md:p-8">

    <div id="toast-container" class="fixed bottom-5 right-5 z-50 flex flex-col gap-2"></div>

    <header class="flex items-center justify-between mb-8 pb-4 border-b border-gray-800">
        <div class="flex items-center gap-3">
            <div class="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                <i data-lucide="satellite" class="w-6 h-6 text-emerald-400"></i>
            </div>
            <div>
                <h1 class="text-2xl font-bold text-white tracking-tight">Fleet Command</h1>
                <p class="text-xs text-gray-400 font-mono mt-1">v2.0.3 // SECURE_UPLINK</p>
            </div>
        </div>
        <div class="flex gap-4 text-sm font-mono text-gray-400">
            <div class="flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> SYSTEM ONLINE</div>
        </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow">
        <!-- LEFT COLUMN: Workers & Inputs -->
        <div class="lg:col-span-5 flex flex-col gap-6">
            <div class="glass-panel rounded-xl p-5 shadow-xl">
                <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <i data-lucide="terminal-square" class="w-4 h-4"></i> Execute Payload
                </h2>
                
                <div class="flex bg-gray-900 border border-gray-700 rounded-lg overflow-hidden focus-within:border-emerald-500 transition-colors">
                    <span class="px-3 py-3 text-emerald-500 font-mono border-r border-gray-700 bg-gray-800/50">>_</span>
                    <input type="text" id="commandInput" placeholder="bash / powershell command..." 
                        class="w-full bg-transparent text-gray-100 font-mono px-3 py-2 outline-none placeholder-gray-600" autocomplete="off" autofocus>
                    <button id="sendBtn" class="bg-emerald-600 hover:bg-emerald-500 text-white px-4 font-semibold transition-colors flex items-center gap-2">
                        Deploy <i data-lucide="send" class="w-4 h-4"></i>
                    </button>
                </div>

                <div class="mt-4">
                    <h3 class="text-xs text-gray-500 font-mono mb-2">RECENT COMMANDS</h3>
                    <div id="commandHistory" class="flex flex-col gap-1.5 font-mono text-xs">
                        <div class="text-gray-600 italic">No commands sent in this session.</div>
                    </div>
                </div>
            </div>

            <div class="glass-panel rounded-xl p-5 shadow-xl flex-grow">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                        <i data-lucide="network" class="w-4 h-4"></i> Active Nodes
                    </h2>
                    <span id="workerCount" class="bg-gray-800 text-xs px-2 py-1 rounded-md border border-gray-700">0</span>
                </div>
                
                <div id="workersList" class="flex flex-col gap-3 max-h-[400px] overflow-y-auto pr-2">
                    <div class="text-gray-500 italic text-sm">Loading nodes...</div>
                </div>
            </div>
        </div>

        <!-- RIGHT COLUMN: Queues and Logs -->
        <div class="lg:col-span-7 flex flex-col gap-6">
            <div class="glass-panel rounded-xl p-5 shadow-xl">
                <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <i data-lucide="list-todo" class="w-4 h-4"></i> Pending Queue
                </h2>
                <div id="tasksList" class="space-y-2 font-mono text-sm max-h-[150px] overflow-y-auto">
                    <div class="text-gray-500 italic">Queue is currently empty.</div>
                </div>
            </div>

            <div class="glass-panel rounded-xl p-0 shadow-xl flex flex-col flex-grow border border-gray-700 overflow-hidden">
                <div class="bg-gray-800/80 border-b border-gray-700 px-4 py-2 flex justify-between items-center">
                    <h2 class="text-sm font-semibold text-gray-300 flex items-center gap-2">
                        <i data-lucide="activity" class="w-4 h-4"></i> Live Telemetry
                    </h2>
                    <div class="flex gap-2">
                        <div class="w-3 h-3 rounded-full bg-gray-600"></div>
                        <div class="w-3 h-3 rounded-full bg-gray-600"></div>
                        <div class="w-3 h-3 rounded-full bg-gray-600"></div>
                    </div>
                </div>
                <div id="resultsList" class="p-4 bg-[#0a0f18] text-gray-300 font-mono text-sm overflow-y-auto flex-grow max-h-[500px] space-y-4">
                    <div class="text-gray-600">Awaiting telemetry data...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();
        let history =[];

        function escapeHTML(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Applied User's UTC-matching logic
        const timeAgo = (dateStr) => {
            if (!dateStr) return "Unknown";
            const now = new Date();
            // Get current UTC timestamp in milliseconds
            const utcNow = Date.UTC(
                now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
                now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds()
            );
            const then = new Date(dateStr).getTime();
            const seconds = Math.floor((utcNow - then) / 1000);
            
            if (seconds < 60) return "Just now";
            if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
            return Math.floor(seconds / 3600) + "h ago";
        };

        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const bg = type === 'success' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-red-500/20 border-red-500/50 text-red-400';
            toast.className = `px-4 py-3 rounded-lg border ${bg} backdrop-blur-md shadow-lg font-mono text-sm flex items-center gap-2 transition-all duration-300 translate-y-10 opacity-0`;
            toast.innerHTML = `<i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}" class="w-4 h-4"></i> ${message}`;
            container.appendChild(toast);
            lucide.createIcons();
            
            setTimeout(() => toast.classList.remove('translate-y-10', 'opacity-0'), 10);
            setTimeout(() => {
                toast.classList.add('opacity-0');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        async function fetchSafeJSON(url) {
            try {
                const res = await fetch(url);
                const text = await res.text();
                return text ? JSON.parse(text) :[];
            } catch (err) {
                console.error(`Error parsing data from ${url}:`, err);
                return[];
            }
        }

        async function updateData() {
            const tasks = await fetchSafeJSON('/api/tasks');
            const results = await fetchSafeJSON('/api/results');
            const workers = await fetchSafeJSON('/api/workers');

            const tasksContainer = document.getElementById('tasksList');
            if (tasks.length === 0) {
                tasksContainer.innerHTML = '<div class="text-gray-600 italic">Queue is empty.</div>';
            } else {
                tasksContainer.innerHTML = tasks.map(t => `
                    <div class="flex items-center gap-3 bg-gray-800/50 p-2 rounded border border-gray-700/50">
                        <span class="text-emerald-500 font-bold min-w-[30px]">#${t.id}</span>
                        <span class="text-gray-300 truncate">${escapeHTML(t.command)}</span>
                    </div>
                `).reverse().join('');
            }

            const resultsContainer = document.getElementById('resultsList');
            const wasScrolledToBottom = resultsContainer.scrollHeight - resultsContainer.clientHeight <= resultsContainer.scrollTop + 10;
            
            if (results.length === 0) {
                resultsContainer.innerHTML = '<div class="text-gray-600">Awaiting telemetry data...</div>';
            } else {
                resultsContainer.innerHTML = results.map(r => {
                    const output = r.output || r.result || JSON.stringify(r);
                    return `
                    <div class="border-l-2 border-emerald-500/30 pl-3 mb-4">
                        <div class="flex justify-between items-center mb-1 text-xs">
                            <span class="text-emerald-400 font-bold">Node: ${escapeHTML(r.worker || r.ip || r.hostname || 'Unknown')}</span>
                            <span class="text-gray-500">Task #${escapeHTML(r.id || '?')}</span>
                        </div>
                        <div class="text-gray-300 whitespace-pre-wrap break-all">${escapeHTML(output)}</div>
                    </div>
                `}).reverse().join('');
            }
            
            if (wasScrolledToBottom) {
                resultsContainer.scrollTop = resultsContainer.scrollHeight;
            }

            const workersContainer = document.getElementById('workersList');
            document.getElementById('workerCount').innerText = workers.length;
            
            if (workers.length === 0) {
                workersContainer.innerHTML = '<div class="text-gray-500 italic text-sm">No nodes connected.</div>';
            } else {
                // Apply User's exact UTC mapping for calculating Online/Offline status
                const now = new Date();
                const utcNow = Date.UTC(
                    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
                    now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds()
                );

                workersContainer.innerHTML = workers.map(w => {
                    const lastSeenMs = w.lastSeen ? new Date(w.lastSeen).getTime() : 0;
                    // Check if node pinged in the last 5 minutes (300,000 ms) using matched UTC logic
                    const isOnline = ((utcNow - lastSeenMs) / 60000) < 5;
                    
                    return `
                    <div class="bg-gray-800/40 border border-gray-700 p-3 rounded-lg flex items-center justify-between hover:bg-gray-800 transition-colors">
                        <div class="flex flex-col">
                            <span class="font-bold text-gray-200 text-sm flex items-center gap-2">
                                <i data-lucide="server" class="w-3 h-3 text-gray-400"></i> 
                                ${escapeHTML(w.hostname || w.name || w.ip || 'Unknown Node')}
                            </span>
                            <span class="text-xs text-gray-500 mt-1">${escapeHTML(w.ip)} • ${escapeHTML(w.os || 'N/A')}</span>
                        </div>
                        <div class="flex flex-col items-end">
                            <span class="flex items-center gap-1.5 text-xs ${isOnline ? 'text-emerald-400' : 'text-red-400'}">
                                <span class="w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}"></span>
                                ${isOnline ? 'ONLINE' : 'OFFLINE'}
                            </span>
                            <span class="text-[10px] text-gray-500 mt-1">${timeAgo(w.lastSeen)}</span>
                        </div>
                    </div>
                `}).join('');
                lucide.createIcons();
            }
        }

        setInterval(updateData, 3000);
        updateData();

        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');
        const historyDiv = document.getElementById('commandHistory');

        async function executeCommand() {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;
            
            cmdInput.disabled = true;
            sendBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Sending`;
            lucide.createIcons();

            try {
                const res = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });

                if(res.ok) {
                    showToast('Payload deployed to queue.', 'success');
                    history.unshift(cmd);
                    if (history.length > 4) history.pop();
                    historyDiv.innerHTML = history.map(c => `
                        <div class="bg-gray-900 px-2 py-1.5 rounded border border-gray-800 flex items-center gap-2">
                            <span class="text-emerald-500 opacity-50">></span> ${escapeHTML(c)}
                        </div>
                    `).join('');
                    cmdInput.value = '';
                } else {
                    showToast('Failed to deploy payload.', 'error');
                }
            } catch (e) {
                showToast('Network error.', 'error');
            }

            cmdInput.disabled = false;
            sendBtn.innerHTML = `Deploy <i data-lucide="send" class="w-4 h-4"></i>`;
            lucide.createIcons();
            cmdInput.focus();
            updateData();
        }

        sendBtn.onclick = executeCommand;
        cmdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executeCommand();
        });
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
    data['lastSeen'] = datetime.utcnow().isoformat()
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
    print("Dashboard started on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)

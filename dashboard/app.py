import json
import os
import sys
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# ----------------------------------------------------------------------
# Data directory – persistent for the run (6h)
# ----------------------------------------------------------------------
DATA_DIR = os.environ.get('WEBAPP_DATA', r'C:\webapp')
os.makedirs(DATA_DIR, exist_ok=True)

TASKS_FILE = os.path.join(DATA_DIR, 'tasks.json')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')
WORKERS_FILE = os.path.join(DATA_DIR, 'workers.json')

# Ensure files exist
for f in[TASKS_FILE, RESULTS_FILE, WORKERS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as fp:
            json.dump([], fp)

# ----------------------------------------------------------------------
# HTML Template – Modern UI/UX Dashboard
# ----------------------------------------------------------------------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetBird Fleet Command</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --panel-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #10b981;
            --accent-hover: #059669;
            --danger: #ef4444;
        }
        
        * { box-sizing: border-box; }
        
        body { 
            font-family: 'Inter', system-ui, -apple-system, sans-serif; 
            margin: 0; 
            background: var(--bg-color); 
            color: var(--text-main); 
            padding: 20px;
        }

        .header {
            display: flex;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--panel-border);
        }

        h1 { margin: 0; font-size: 1.5rem; color: var(--accent); display: flex; align-items: center; gap: 10px; }
        h2 { margin: 0 0 16px 0; font-size: 1.1rem; color: var(--text-main); font-weight: 600; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .panel { 
            background: var(--panel-bg); 
            border: 1px solid var(--panel-border); 
            border-radius: 12px; 
            padding: 20px; 
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        /* Full width panels */
        .panel.full-width { grid-column: 1 / -1; }

        /* Command Input styling */
        .command-wrapper {
            display: flex;
            gap: 10px;
            background: #0b1120;
            padding: 8px;
            border-radius: 8px;
            border: 1px solid var(--panel-border);
            align-items: center;
        }
        
        .prompt { color: var(--accent); font-family: monospace; padding-left: 10px; font-weight: bold;}
        
        input[type="text"] { 
            background: transparent; 
            color: var(--text-main); 
            border: none; 
            padding: 10px; 
            width: 100%; 
            font-family: monospace;
            font-size: 1rem;
            outline: none; 
        }

        button { 
            background: var(--accent); 
            color: #000; 
            border: none; 
            border-radius: 6px;
            padding: 10px 20px; 
            font-weight: 600;
            cursor: pointer; 
            transition: all 0.2s;
        }
        
        button:hover { background: var(--accent-hover); }
        button:active { transform: scale(0.97); }

        .cmd-history { 
            margin-top: 16px; 
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        
        .history-item {
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--text-muted);
            background: rgba(255,255,255,0.05);
            padding: 6px 10px;
            border-radius: 4px;
        }

        /* Workers list */
        .worker-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
        
        .worker-card { 
            background: #0b1120; 
            border: 1px solid var(--panel-border); 
            border-radius: 8px; 
            padding: 12px;
            position: relative;
        }

        .worker-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;}
        .worker-title { font-weight: bold; color: var(--accent); font-family: monospace;}
        
        .status-dot {
            height: 10px; width: 10px;
            background-color: var(--accent);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--accent);
        }
        .status-dot.offline { background-color: var(--danger); box-shadow: 0 0 8px var(--danger); }

        .worker-info { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

        /* Data views */
        .data-container {
            flex-grow: 1;
            max-height: 300px;
            overflow-y: auto;
            background: #0b1120;
            border-radius: 8px;
            border: 1px solid var(--panel-border);
            padding: 10px;
        }

        .task-item, .result-item {
            border-bottom: 1px solid var(--panel-border);
            padding: 8px 0;
            font-size: 0.9rem;
        }
        .task-item:last-child, .result-item:last-child { border-bottom: none; }
        
        .item-id { color: var(--accent); font-family: monospace; margin-right: 10px; font-weight: bold;}
        .item-cmd { font-family: monospace; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;}
        
        .result-output {
            margin-top: 8px;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--text-muted);
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--panel-border); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
</head>
<body>
    <div class="header">
        <h1><span style="font-size: 1.8rem;">🛸</span> NetBird Fleet Command</h1>
    </div>

    <div class="dashboard-grid">
        
        <!-- Workers Panel -->
        <div class="panel full-width">
            <h2>Active Workers</h2>
            <div id="workersList" class="worker-list">
                <div style="color: var(--text-muted);">Loading workers...</div>
            </div>
        </div>

        <!-- Command Panel -->
        <div class="panel full-width">
            <h2>Execute Command</h2>
            <div class="command-wrapper">
                <span class="prompt">>_</span>
                <input type="text" id="commandInput" placeholder="Enter PowerShell / Bash command..." autocomplete="off" autofocus>
                <button id="sendBtn">Deploy Task</button>
            </div>
            <div id="commandHistory" class="cmd-history"></div>
        </div>

        <!-- Pending Tasks Panel -->
        <div class="panel">
            <h2>Pending Tasks Queue</h2>
            <div class="data-container" id="tasksList">
                <div style="color: var(--text-muted);">Loading tasks...</div>
            </div>
        </div>

        <!-- Results Panel -->
        <div class="panel">
            <h2>Execution Results</h2>
            <div class="data-container" id="resultsList">
                <div style="color: var(--text-muted);">Loading results...</div>
            </div>
        </div>

    </div>

    <script>
        let history =[];

        function formatTime(isoString) {
            if (!isoString) return 'Unknown';
            const date = new Date(isoString);
            return date.toLocaleTimeString() + ' ' + date.toLocaleDateString();
        }

        function updateData() {
            // Fetch Tasks
            fetch('/api/tasks').then(r => r.json()).then(data => {
                const container = document.getElementById('tasksList');
                if (data.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted); padding: 10px;">Queue is empty.</div>';
                    return;
                }
                container.innerHTML = data.map(t => `
                    <div class="task-item">
                        <span class="item-id">#${t.id}</span>
                        <span class="item-cmd">${t.command}</span>
                    </div>
                `).reverse().join('');
            });

            // Fetch Results
            fetch('/api/results').then(r => r.json()).then(data => {
                const container = document.getElementById('resultsList');
                if (data.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted); padding: 10px;">No results yet.</div>';
                    return;
                }
                container.innerHTML = data.map(r => {
                    // Fallback to JSON if format is unknown
                    const output = r.output || r.result || JSON.stringify(r, null, 2);
                    return `
                    <div class="result-item">
                        <div>
                            <span class="item-id">#${r.id || '?'}</span>
                            <span style="color: var(--text-muted); font-size: 0.8rem;">
                                From: ${r.worker || r.ip || r.hostname || 'Unknown'}
                            </span>
                        </div>
                        <div class="result-output">${output}</div>
                    </div>
                `}).reverse().join('');
            });

            // Fetch Workers
            fetch('/api/workers').then(r => r.json()).then(data => {
                const container = document.getElementById('workersList');
                if (data.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted);">No workers registered yet.</div>';
                    return;
                }
                
                const now = new Date();
                container.innerHTML = data.map(w => {
                    // Check if seen in last 5 minutes to mark active
                    const lastSeenDate = new Date(w.lastSeen);
                    const diffMins = (now - lastSeenDate) / 1000 / 60;
                    const isOnline = diffMins < 5;
                    const statusClass = isOnline ? '' : 'offline';
                    const title = w.hostname || w.name || w.ip || 'Unknown Node';

                    return `
                    <div class="worker-card">
                        <div class="worker-header">
                            <span class="worker-title">${title}</span>
                            <span class="status-dot ${statusClass}" title="${isOnline ? 'Online' : 'Offline'}"></span>
                        </div>
                        <div class="worker-info">IP: ${w.ip || 'N/A'}</div>
                        <div class="worker-info">OS: ${w.os || 'N/A'}</div>
                        <div class="worker-info">Seen: ${formatTime(w.lastSeen)}</div>
                    </div>
                `}).join('');
            });
        }

        // Poll every 3 seconds
        setInterval(updateData, 3000);
        updateData();

        // Command Execution Logic
        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');
        const historyDiv = document.getElementById('commandHistory');

        sendBtn.onclick = async () => {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;
            
            // Visual feedback on button
            const originalText = sendBtn.innerText;
            sendBtn.innerText = "Sending...";
            
            await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });
            
            sendBtn.innerText = originalText;

            // Update history UI
            history.unshift(cmd);
            if (history.length > 5) history.pop(); // Keep last 5
            historyDiv.innerHTML = history.map(c => `<div class="history-item">> ${c}</div>`).join('');
            cmdInput.value = '';
            
            // Force an immediate UI update
            updateData();
        };

        cmdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendBtn.click();
        });
    </script>
</body>
</html>
'''

# ----------------------------------------------------------------------
# Flask app
# ----------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# ----------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    with open(TASKS_FILE, 'r') as f:
        tasks = json.load(f)
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json
    if not data or 'command' not in data:
        return 'Missing command', 400
    with open(TASKS_FILE, 'r+') as f:
        tasks = json.load(f)
        task_id = len(tasks) + 1
        new_task = {'id': task_id, 'command': data['command']}
        tasks.append(new_task)
        f.seek(0)
        json.dump(tasks, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/tasks/pop', methods=['GET'])
def pop_task():
    with open(TASKS_FILE, 'r+') as f:
        tasks = json.load(f)
        if tasks:
            task = tasks.pop(0)
            f.seek(0)
            json.dump(tasks, f, indent=2)
            f.truncate()
            return jsonify(task)
        else:
            return '', 204

@app.route('/api/results', methods=['POST'])
def add_result():
    result = request.json
    with open(RESULTS_FILE, 'r+') as f:
        results = json.load(f)
        results.append(result)
        f.seek(0)
        json.dump(results, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/results', methods=['GET'])
def get_results():
    with open(RESULTS_FILE, 'r') as f:
        results = json.load(f)
    return jsonify(results)

@app.route('/api/workers', methods=['POST'])
def register_worker():
    data = request.json
    if not data:
        return 'Missing data', 400
    # Add timestamp
    data['lastSeen'] = datetime.utcnow().isoformat()
    with open(WORKERS_FILE, 'r+') as f:
        workers = json.load(f)
        # Update existing worker or add new
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
    with open(WORKERS_FILE, 'r') as f:
        workers = json.load(f)
    return jsonify(workers)

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == '__main__':
    print("Dashboard starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)

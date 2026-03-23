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
for f in [TASKS_FILE, RESULTS_FILE, WORKERS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as fp:
            json.dump([], fp)

# ----------------------------------------------------------------------
# HTML Template – modern dark theme with worker cards and command history
# ----------------------------------------------------------------------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>NetBird Fleet Dashboard</title>
    <style>
        body { font-family: monospace; margin: 20px; background: #0a0a0a; color: #0f0; }
        h1, h2 { color: #0f0; }
        .section { background: #111; border: 1px solid #0f0; border-radius: 5px; padding: 15px; margin-bottom: 20px; }
        pre { background: #000; color: #0f0; padding: 10px; overflow-x: auto; border: 1px solid #0f0; }
        input, textarea { background: #000; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 100%; }
        button { background: #0f0; color: #000; border: none; padding: 5px 10px; cursor: pointer; }
        button:hover { background: #0a0; }
        .worker-list { display: flex; flex-wrap: wrap; gap: 10px; }
        .worker-card { background: #111; border: 1px solid #0f0; padding: 5px; width: 200px; }
        .online { color: #0f0; }
        .offline { color: #f00; }
        .cmd-history { font-size: 0.8em; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>🛸 NetBird Fleet Command</h1>
    <div class="section">
        <h2>Send Command</h2>
        <input type="text" id="commandInput" placeholder="Enter PowerShell command..." autofocus>
        <button id="sendBtn">Execute</button>
        <div id="commandHistory" class="cmd-history"></div>
    </div>
    <div class="section">
        <h2>Workers</h2>
        <div id="workersList" class="worker-list">Loading...</div>
    </div>
    <div class="section">
        <h2>Pending Tasks</h2>
        <pre id="tasks">Loading...</pre>
    </div>
    <div class="section">
        <h2>Results</h2>
        <pre id="results">Loading...</pre>
    </div>

    <script>
        let history = [];

        function updateData() {
            fetch('/api/tasks').then(r => r.json()).then(data => {
                document.getElementById('tasks').innerText = JSON.stringify(data, null, 2);
            });
            fetch('/api/results').then(r => r.json()).then(data => {
                document.getElementById('results').innerText = JSON.stringify(data, null, 2);
            });
            fetch('/api/workers').then(r => r.json()).then(data => {
                const html = data.map(w => `
                    <div class="worker-card">
                        <div><b>${w.hostname || w.name || w.ip}</b></div>
                        <div>IP: ${w.ip}</div>
                        <div>OS: ${w.os || '?'}</div>
                        <div>Last seen: ${w.lastSeen || '?'}</div>
                    </div>
                `).join('');
                document.getElementById('workersList').innerHTML = html || '<div>No workers yet</div>';
            });
        }
        setInterval(updateData, 3000);
        updateData();

        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');
        const historyDiv = document.getElementById('commandHistory');

        sendBtn.onclick = async () => {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;
            await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });
            history.unshift(cmd);
            if (history.length > 10) history.pop();
            historyDiv.innerHTML = history.map(c => `<div>${c}</div>`).join('');
            cmdInput.value = '';
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

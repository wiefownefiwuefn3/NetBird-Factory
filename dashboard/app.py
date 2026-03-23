import json
import os
from flask import Flask, request, jsonify, render_template_string

# Determine data directory from environment (set in workflow) or use default
DATA_DIR = os.environ.get('WEBAPP_DATA', r'C:\webapp')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# File paths
TASKS_FILE = os.path.join(DATA_DIR, 'tasks.json')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')
WORKERS_FILE = os.path.join(DATA_DIR, 'workers.json')

# Ensure files exist
for f in [TASKS_FILE, RESULTS_FILE, WORKERS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as fp:
            json.dump([], fp)

# Simple HTML template for the dashboard
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>NetBird Fleet Dashboard</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #f0f0f0; }
        h1, h2 { color: #333; }
        .section { background: white; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        pre { background: #eee; padding: 10px; overflow: auto; }
        input, textarea { width: 100%; padding: 8px; margin: 5px 0; }
        button { background: #007bff; color: white; border: none; padding: 8px 15px; cursor: pointer; border-radius: 4px; }
        button:hover { background: #0056b3; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>NetBird Fleet Dashboard</h1>
    <div class="section">
        <h2>Add New Task</h2>
        <form id="taskForm">
            <input type="text" id="taskCmd" placeholder="Command (e.g., echo Hello)" required>
            <button type="submit">Add Task</button>
        </form>
    </div>

    <div class="section">
        <h2>Pending Tasks</h2>
        <pre id="tasks">Loading...</pre>
    </div>

    <div class="section">
        <h2>Results</h2>
        <pre id="results">Loading...</pre>
    </div>

    <div class="section">
        <h2>Workers</h2>
        <pre id="workers">Loading...</pre>
    </div>

    <script>
        function fetchData() {
            fetch('/api/tasks').then(r => r.json()).then(data => {
                document.getElementById('tasks').innerText = JSON.stringify(data, null, 2);
            });
            fetch('/api/results').then(r => r.json()).then(data => {
                document.getElementById('results').innerText = JSON.stringify(data, null, 2);
            });
            fetch('/api/workers').then(r => r.json()).then(data => {
                document.getElementById('workers').innerText = JSON.stringify(data, null, 2);
            });
        }
        setInterval(fetchData, 3000);
        fetchData();

        document.getElementById('taskForm').onsubmit = async (e) => {
            e.preventDefault();
            const cmd = document.getElementById('taskCmd').value;
            await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });
            document.getElementById('taskCmd').value = '';
            fetchData();
        };
    </script>
</body>
</html>
'''

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# API endpoints
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
    if data and 'ip' in data:
        with open(WORKERS_FILE, 'r+') as f:
            workers = json.load(f)
            if not any(w.get('ip') == data['ip'] for w in workers):
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

if __name__ == '__main__':
    # Add a print to confirm the server is about to start
    print("Server is now starting...")
    import sys
    sys.stdout.flush()
    app.run(host='0.0.0.0', port=5000, debug=False)

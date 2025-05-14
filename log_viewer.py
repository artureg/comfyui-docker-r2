from flask import Flask, render_template_string, make_response, jsonify, send_file, request
import os
import threading
import time
import subprocess
import sys
import platform
import zipfile
import io
import urllib.parse
from flask_socketio import SocketIO, emit
from datetime import datetime

# Initialize Flask and SocketIO with CORS
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables to store logs
log_buffer = []
log_lock = threading.Lock()

# Add HTML_TEMPLATE before the routes
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ComfyUI Log Viewer</title>
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2563eb;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
            --progress-bg: #e2e8f0;
            --scrollbar-track: #f1f1f1;
            --scrollbar-thumb: #c1c1c1;
            --scrollbar-thumb-hover: #a8a8a8;
        }

        [data-theme="dark"] {
            --primary-color: #3b82f6;
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #e2e8f0;
            --text-secondary: #94a3b8;
            --border-color: #334155;
            --progress-bg: #334155;
            --scrollbar-track: #1e293b;
            --scrollbar-thumb: #475569;
            --scrollbar-thumb-hover: #64748b;
        }
        
        body { 
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 0;
            background: var(--bg-color);
            color: var(--text-color);
            transition: background-color 0.3s, color 0.3s;
        }
        
        .container {
            display: grid;
            grid-template-columns: 300px 1fr;
            grid-template-rows: auto 1fr;
            height: 100vh;
            width: 100%;
        }
        
        .header {
            grid-column: 1 / -1;
            padding: 16px 24px;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .header-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-color);
            margin: 0;
        }
        
        .header-controls {
            display: flex;
            gap: 16px;
            align-items: center;
        }
        
        .sidebar {
            grid-row: 2;
            grid-column: 1;
            background: var(--card-bg);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        
        .main-content {
            grid-row: 2;
            grid-column: 2;
            display: grid;
            grid-template-rows: 1fr auto;
            overflow: hidden;
        }
        
        .logs-container {
            padding: 20px;
            overflow-y: auto;
            background: var(--bg-color);
        }
        
        #log-container {
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            color: var(--text-color);
            padding: 16px;
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        
        .download-panel {
            padding: 20px;
            background: var(--card-bg);
            border-top: 1px solid var(--border-color);
        }
        
        .section {
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
            color: var(--text-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .section-content {
            background: var(--bg-color);
            border-radius: 8px;
            padding: 12px;
        }
        
        .list-item {
            font-size: 14px;
            padding: 6px 0;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-color);
        }
        
        .list-item:last-child {
            border-bottom: none;
        }
        
        .model-category {
            margin-bottom: 16px;
        }
        
        .category-name {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 8px;
            color: var(--text-color);
        }
        
        .button {
            display: inline-flex;
            align-items: center;
            padding: 8px 16px;
            background: var(--primary-color);
            color: white;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            transition: background-color 0.3s;
            border: none;
            cursor: pointer;
            font-size: 14px;
        }
        
        .button:hover {
            background-color: #1d4ed8;
        }
        
        .button.secondary {
            background-color: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-color);
        }
        
        .button.secondary:hover {
            background-color: var(--bg-color);
        }
        
        .button.success {
            background-color: #10b981;
        }
        
        .button.success:hover {
            background-color: #059669;
        }
        
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--progress-bg);
            transition: .4s;
            border-radius: 24px;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: var(--card-bg);
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .toggle-slider {
            background-color: var(--primary-color);
        }
        
        input:checked + .toggle-slider:before {
            transform: translateX(20px);
        }
        
        .theme-switch {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .auto-scroll-control {
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 1000;
            background: var(--card-bg);
            padding: 8px 16px;
            border-radius: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            color: var(--text-color);
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-color);
            font-weight: 500;
            font-size: 14px;
        }
        
        .form-group input[type="text"],
        .form-group input[type="url"],
        .form-group select {
            width: 100%;
            max-width: 400px;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--bg-color);
            color: var(--text-color);
            font-size: 14px;
        }
        
        .form-group .example-text {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }
        
        .download-tabs {
            display: flex;
            gap: 2px;
            margin-bottom: 16px;
        }
        
        .download-tab {
            padding: 8px 16px;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px 6px 0 0;
            cursor: pointer;
            font-size: 14px;
        }
        
        .download-tab.active {
            background: var(--card-bg);
            border-bottom-color: transparent;
            font-weight: 500;
        }
        
        .download-content {
            display: none;
            padding: 16px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 0 6px 6px 6px;
        }
        
        .download-content.active {
            display: block;
        }
        
        .status-message {
            margin-top: 12px;
            padding: 12px;
            border-radius: 6px;
            display: none;
        }
        
        .status-success {
            background: #dcfce7;
            color: #166534;
        }
        
        .status-error {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .notification {
            margin-top: 10px;
            padding: 12px;
            border-radius: 6px;
            background: #f0f9ff;
            color: #0369a1;
            display: none;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--scrollbar-track);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--scrollbar-thumb);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--scrollbar-thumb-hover);
        }
        
        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
                grid-template-rows: auto auto 1fr;
            }
            
            .sidebar {
                grid-row: 2;
                grid-column: 1;
                border-right: none;
                border-bottom: 1px solid var(--border-color);
                padding: 12px;
            }
            
            .main-content {
                grid-row: 3;
                grid-column: 1;
            }
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        let socket;
        let autoScroll = true;
        let userScrolled = false;

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            const themeToggle = document.getElementById('theme-toggle');
            
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            document.getElementById('theme-icon').textContent = 
                newTheme === 'dark' ? '🌙' : '☀️';
            
            themeToggle.checked = newTheme === 'dark';
        }

        function initializeTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            const themeToggle = document.getElementById('theme-toggle');
            
            document.documentElement.setAttribute('data-theme', savedTheme);
            document.getElementById('theme-icon').textContent = 
                savedTheme === 'dark' ? '🌙' : '☀️';
            themeToggle.checked = savedTheme === 'dark';
        }

        function initializeWebSocket() {
            socket = io();
            
            socket.on('new_log_line', function(data) {
                appendLogLine(data.line);
            });
            
            socket.on('logs', function(data) {
                document.getElementById('log-container').innerHTML = data.logs;
                if (autoScroll) {
                    scrollToBottom(document.getElementById('log-container'));
                }
            });
        }
        
        function appendLogLine(line) {
            const logContainer = document.getElementById('log-container');
            logContainer.innerHTML += line + '\\n';
            
            if (autoScroll && !userScrolled) {
                scrollToBottom(logContainer);
            }
        }
        
        function scrollToBottom(element) {
            element.scrollTop = element.scrollHeight;
        }
        
        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            userScrolled = false;
            if (autoScroll) {
                const logContainer = document.getElementById('log-container');
                scrollToBottom(logContainer);
            }
        }
        
        function switchDownloadTab(tabId) {
            // Hide all content
            const contents = document.querySelectorAll('.download-content');
            contents.forEach(content => content.classList.remove('active'));
            
            // Deactivate all tabs
            const tabs = document.querySelectorAll('.download-tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Activate selected tab and content
            document.getElementById(tabId).classList.add('active');
            document.getElementById(tabId + '-content').classList.add('active');
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            initializeTheme();
            initializeWebSocket();
            
            const logContainer = document.getElementById('log-container');
            
            logContainer.addEventListener('scroll', function() {
                if (!isScrolledToBottom(logContainer)) {
                    userScrolled = true;
                } else {
                    userScrolled = false;
                }
            });
            
            scrollToBottom(logContainer);
            
            // Check if ComfyUI is running
            checkComfyUIStatus();
            
            // Initialize first download tab
            switchDownloadTab('civitai-tab');
        });

        function isScrolledToBottom(element) {
            return Math.abs(element.scrollHeight - element.scrollTop - element.clientHeight) < 1;
        }
        
        function checkComfyUIStatus() {
            const comfyUrl = '{{ proxy_url }}';
            const statusElement = document.getElementById('comfyui-status');
            
            fetch(comfyUrl, { method: 'HEAD', mode: 'no-cors' })
                .then(() => {
                    // If we get here, the request didn't throw an error
                    statusElement.style.display = 'none';
                    document.getElementById('comfyui-button').classList.remove('disabled');
                })
                .catch(() => {
                    // Show notification that ComfyUI might not be ready
                    statusElement.style.display = 'block';
                    statusElement.textContent = 'ComfyUI may still be starting. Check logs for progress.';
                    // Check again in 10 seconds
                    setTimeout(checkComfyUIStatus, 10000);
                });
        }

        function refreshLogs() {
            fetch('/refresh_logs')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Logs refreshed successfully');
                    } else {
                        console.error('Error refreshing logs:', data.message);
                    }
                })
                .catch(error => {
                    console.error('Failed to refresh logs:', error);
                });
        }

        function downloadFromCivitai() {
            const url = document.getElementById('modelUrl').value;
            const apiKey = document.getElementById('apiKey').value;
            const modelType = document.getElementById('modelType').value;
            const statusDiv = document.getElementById('downloadStatus');
            
            statusDiv.className = 'status-message';
            statusDiv.style.display = 'block';
            statusDiv.textContent = 'Downloading...';
            
            fetch('/download/civitai', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    api_key: apiKey,
                    model_type: modelType
                })
            })
            .then(response => response.json())
            .then(data => {
                statusDiv.textContent = data.message;
                statusDiv.className = data.success ? 'status-message status-success' : 'status-message status-error';
            })
            .catch(error => {
                statusDiv.textContent = 'Error: ' + error.message;
                statusDiv.className = 'status-message status-error';
            });
        }

        function downloadFromHuggingFace() {
            const url = document.getElementById('hfUrl').value;
            const modelType = document.getElementById('hfModelType').value;
            const statusDiv = document.getElementById('hfDownloadStatus');
            
            statusDiv.className = 'status-message';
            statusDiv.style.display = 'block';
            statusDiv.textContent = 'Downloading...';
            
            fetch('/download/huggingface', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    model_type: modelType
                })
            })
            .then(response => response.json())
            .then(data => {
                statusDiv.textContent = data.message;
                statusDiv.className = data.success ? 'status-message status-success' : 'status-message status-error';
            })
            .catch(error => {
                statusDiv.textContent = 'Error: ' + error.message;
                statusDiv.className = 'status-message status-error';
            });
        }
    </script>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1 class="header-title">ComfyUI Log Viewer</h1>
            <div class="header-controls">
                <a href="{{ proxy_url }}" target="_blank" id="comfyui-button" class="button success">Open ComfyUI</a>
                <button onclick="refreshLogs()" class="button">Refresh Logs</button>
                <div class="theme-switch">
                    <span id="theme-icon" class="icon">☀️</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="theme-toggle" onchange="toggleTheme()">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>
        </header>
        
        <aside class="sidebar">
            <!-- Custom Nodes Section - Simplified -->
            <div class="section">
                <h2 class="section-title">Installed Custom Nodes <span>({{ custom_nodes|length }})</span></h2>
                <div class="section-content">
                    {% if custom_nodes %}
                        {% for node in custom_nodes %}
                            <div class="list-item">{{ node.name }}</div>
                        {% endfor %}
                    {% else %}
                        <div class="list-item">No custom nodes installed</div>
                    {% endif %}
                </div>
            </div>
            
            <!-- Models Section - Simplified -->
            <div class="section">
                <h2 class="section-title">Installed Models <span>({{ total_models }})</span></h2>
                <div class="section-content">
                    {% if models %}
                        {% for category, items in models.items() %}
                            {% if items %}
                                <div class="model-category">
                                    <div class="category-name">{{ category }} ({{ items|length }})</div>
                                    {% for model in items %}
                                        <div class="list-item">{{ model.name }}</div>
                                    {% endfor %}
                                </div>
                            {% endif %}
                        {% endfor %}
                    {% else %}
                        <div class="list-item">No models found</div>
                    {% endif %}
                </div>
            </div>
            
            <div class="section">
                <a href="/download/outputs" class="button">Download Outputs</a>
                <div id="comfyui-status" class="notification">Checking ComfyUI status...</div>
            </div>
        </aside>
        
        <main class="main-content">
            <div class="logs-container">
                <div id="log-container">{{ logs }}</div>
            </div>
            
            <div class="download-panel">
                <div class="download-tabs">
                    <div id="civitai-tab" class="download-tab active" onclick="switchDownloadTab('civitai-tab')">Civitai Downloader</div>
                    <div id="huggingface-tab" class="download-tab" onclick="switchDownloadTab('huggingface-tab')">Hugging Face Downloader</div>
                </div>
                
                <div id="civitai-tab-content" class="download-content active">
                    <div class="form-group">
                        <label for="modelUrl">Model URL</label>
                        <input type="url" id="modelUrl" placeholder="Enter model URL" required>
                        <div class="example-text">Example: https://civitai.com/api/download/models/1399707</div>
                    </div>
                    <div class="form-group">
                        <label for="apiKey">API Key (Optional)</label>
                        <input type="text" id="apiKey" placeholder="Your Civitai API key">
                    </div>
                    <div class="form-group">
                        <label for="modelType">Model Type</label>
                        <select id="modelType">
                            <option value="diffusion_models">Diffusion Model</option>
                            <option value="loras">LORA</option>
                            <option value="checkpoints">Checkpoint</option>
                            <option value="vae">VAE</option>
                            <option value="unet">UNet</option>
                            <option value="text_encoders">Text Encoder</option>
                        </select>
                    </div>
                    <button onclick="downloadFromCivitai()" class="button">Download Model</button>
                    <div id="downloadStatus" class="status-message"></div>
                </div>
                
                <div id="huggingface-tab-content" class="download-content">
                    <div class="form-group">
                        <label for="hfUrl">Model URL</label>
                        <input type="url" id="hfUrl" placeholder="Enter Hugging Face file URL" required>
                        <div class="example-text">Example: https://huggingface.co/[user]/[repo]/resolve/main/model.safetensors</div>
                    </div>
                    <div class="form-group">
                        <label for="hfModelType">Model Type</label>
                        <select id="hfModelType">
                            <option value="diffusion_models">Diffusion Model</option>
                            <option value="loras">LORA</option>
                            <option value="checkpoints">Checkpoint</option>
                            <option value="vae">VAE</option>
                            <option value="unet">UNet</option>
                            <option value="text_encoders">Text Encoder</option>
                        </select>
                    </div>
                    <button onclick="downloadFromHuggingFace()" class="button">Download Model</button>
                    <div id="hfDownloadStatus" class="status-message"></div>
                </div>
            </div>
        </main>
    </div>

    <div class="auto-scroll-control">
        <span>Auto-scroll</span>
        <label class="toggle-switch">
            <input type="checkbox" checked onchange="toggleAutoScroll()">
            <span class="toggle-slider"></span>
        </label>
    </div>
</body>
</html>
'''

def get_installed_custom_nodes():
    """Get a list of installed custom nodes from start.sh"""
    custom_nodes = []
    
    try:
        # Check multiple possible locations for start.sh
        start_sh_paths = ['/start.sh', './start.sh', '/workspace/start.sh', os.path.join(os.path.dirname(__file__), 'start.sh')]
        start_sh_content = None
        
        for path in start_sh_paths:
            if os.path.exists(path):
                with open(path, 'r') as file:
                    start_sh_content = file.read()
                break
        
        if not start_sh_content:
            print("Warning: start.sh not found in expected locations")
            return []
            
        # Extract git clone lines for custom nodes
        import re
        pattern = r'git clone --depth=1 (https://github.com/[^/]+/([^\.]+)\.git)'
        matches = re.findall(pattern, start_sh_content)
        
        for match in matches:
            repo_url, repo_name = match
            # Extract the actual repository name from the URL
            repo_name_clean = repo_url.split('/')[-1].replace('.git', '')
            
            custom_nodes.append({
                'name': repo_name_clean,
                'path': f"/workspace/ComfyUI/custom_nodes/{repo_name_clean}",
                'version': "Installed",
                'url': repo_url
            })
    except Exception as e:
        print(f"Error parsing custom nodes from start.sh: {e}")
    
    # Sort alphabetically
    return sorted(custom_nodes, key=lambda x: x['name'].lower())

def get_installed_models():
    """Get a list of installed models from models_config.json"""
    models = {}
    
    try:
        # Check multiple possible locations for models_config.json
        config_paths = [
            '/workspace/models_config.json', 
            './models_config.json',
            os.path.join(os.path.dirname(__file__), 'models_config.json')
        ]
        
        model_config = None
        for path in config_paths:
            if os.path.exists(path):
                import json
                with open(path, 'r') as file:
                    model_config = json.load(file)
                break
        
        if not model_config:
            print("Warning: models_config.json not found in expected locations")
            return {}
        
        # Process each model category
        for category, urls in model_config.items():
            if urls:  # Only process non-empty categories
                model_files = []
                for url in urls:
                    # Extract filename from URL
                    filename = url.split('/')[-1]
                    # Add model information
                    model_files.append({
                        'name': filename,
                        'path': f"/workspace/ComfyUI/models/{category}/{filename}",
                        'size': "From config",
                        'url': url
                    })
                
                if model_files:
                    # Sort by name
                    model_files.sort(key=lambda x: x['name'].lower())
                    models[category] = model_files
    except Exception as e:
        print(f"Error parsing models from models_config.json: {e}")
    
    # Sort categories alphabetically
    return dict(sorted(models.items()))

def get_current_logs():
    """Get the current logs from the buffer"""
    with log_lock:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = f"Log Viewer - Last {len(log_buffer)} lines (as of {timestamp})\n"
        header += "=" * 80 + "\n\n"
        
        # Return log buffer with duplicate consecutive lines removed
        if log_buffer:
            filtered_logs = []
            prev_line = None
            for line in log_buffer:
                if line != prev_line:
                    filtered_logs.append(line)
                prev_line = line
            return header + '\n'.join(filtered_logs)
        else:
            return header + "No logs yet."

def tail_log_file():
    """Continuously tail the log file and update the buffer"""
    log_file = os.path.join('logs', 'comfyui.log')
    
    if not os.path.exists(log_file):
        os.makedirs('logs', exist_ok=True)
        open(log_file, 'a').close()
    
    def follow(file_path):
        """Generator function that yields new lines in a file with proper handling of file rotation/truncation"""
        current_position = 0
        while True:
            try:
                # Re-open the file on each iteration to detect file truncation or rotation
                with open(file_path, 'r') as file:
                    # Check if file has been truncated
                    file_size = os.path.getsize(file_path)
                    if file_size < current_position:
                        current_position = 0  # File was truncated, start from beginning
                    
                    # Seek to last position
                    file.seek(current_position)
                    
                    # Read new lines
                    new_lines = file.readlines()
                    if new_lines:
                        current_position = file.tell()
                        for line in new_lines:
                            yield line
                    else:
                        # No new lines, sleep before checking again
                        time.sleep(0.1)
            except Exception as e:
                print(f"Error following log file: {e}")
                time.sleep(1)  # Wait a bit longer on error

    try:
        # Load initial content
        with open(log_file, 'r') as file:
            content = file.readlines()
            processed_content = []
            
            # Keep only the last 500 lines and filter duplicates
            content = content[-500:] if len(content) > 500 else content
            prev_line = None
            for line in content:
                stripped_line = line.strip()
                if stripped_line and stripped_line != prev_line:
                    processed_content.append(stripped_line)
                prev_line = stripped_line
            
            with log_lock:
                log_buffer.clear()
                log_buffer.extend(processed_content)
            
            # Emit initial logs
            socketio.emit('logs', {'logs': get_current_logs()})
        
        # Start the continuous tail
        prev_line = None
        for line in follow(log_file):
            stripped_line = line.strip()
            if stripped_line and stripped_line != prev_line:  # Only process non-empty lines and not duplicates
                with log_lock:
                    log_buffer.append(stripped_line)
                    if len(log_buffer) > 500:
                        log_buffer.pop(0)
                # Emit new log line via WebSocket
                socketio.emit('new_log_line', {'line': stripped_line})
            prev_line = stripped_line
    except Exception as e:
        print(f"Error tailing log file: {e}")
        time.sleep(5)

def create_output_zip():
    """Create a zip file of the ComfyUI output directory"""
    output_dir = os.path.join('/workspace', 'ComfyUI', 'output')
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zf.write(file_path, arcname)
    
    memory_file.seek(0)
    return memory_file

def download_from_civitai(url, api_key=None, model_type="loras"):
    """Download a model from Civitai using aria2c"""
    model_dir = os.path.join('/workspace', 'ComfyUI', 'models', model_type)
    os.makedirs(model_dir, exist_ok=True)
    
    download_url = url
    if api_key:
        download_url = f"{url}?token={api_key}"
    
    cmd = [
        'aria2c',
        '--console-log-level=error',
        '-c',
        '-x', '16',
        '-s', '16',
        '-k', '1M',
        '--file-allocation=none',
        '--optimize-concurrent-downloads=true',
        '--max-connection-per-server=16',
        '--min-split-size=1M',
        '--max-tries=5',
        '--retry-wait=10',
        '--connect-timeout=30',
        '--timeout=600',
        download_url,
        '-d', model_dir
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "message": "Download completed successfully"}
        else:
            return {"success": False, "message": f"Download failed: {result.stderr}"}
    except Exception as e:
        return {"success": False, "message": f"Error during download: {str(e)}"}

def download_from_huggingface(url, model_type="loras"):
    """Download a model from Hugging Face using aria2c"""
    model_dir = os.path.join('/workspace', 'ComfyUI', 'models', model_type)
    os.makedirs(model_dir, exist_ok=True)
    
    try:
        filename = url.split('/')[-1]
        cmd = [
            'aria2c',
            '--console-log-level=error',
            '-c',
            '-x', '16',
            '-s', '16',
            '-k', '1M',
            '--file-allocation=none',
            '--optimize-concurrent-downloads=true',
            '--max-connection-per-server=16',
            '--min-split-size=1M',
            '--max-tries=5',
            '--retry-wait=10',
            '--connect-timeout=30',
            '--timeout=600',
            url,
            '-d', model_dir,
            '-o', filename
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "message": "Download completed successfully"}
        else:
            return {"success": False, "message": f"Download failed: {result.stderr}"}
    except Exception as e:
        return {"success": False, "message": f"Error during download: {str(e)}"}

@app.route('/api/custom-nodes')
def api_custom_nodes():
    """API endpoint to get installed custom nodes"""
    return jsonify(get_installed_custom_nodes())

@app.route('/api/models')
def api_models():
    """API endpoint to get installed models"""
    return jsonify(get_installed_models())

@app.route('/logs')
def get_logs():
    return jsonify({'logs': get_current_logs()})

@app.route('/refresh_logs')
def refresh_logs():
    """Force a refresh of the logs. Useful when log file has been externally updated."""
    try:
        with log_lock:
            log_buffer.clear()
        
        # Reload logs from file
        log_file = os.path.join('logs', 'comfyui.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as file:
                content = file.readlines()
                processed_content = []
                
                # Keep only the last 500 lines and filter duplicates
                content = content[-500:] if len(content) > 500 else content
                prev_line = None
                for line in content:
                    stripped_line = line.strip()
                    if stripped_line and stripped_line != prev_line:
                        processed_content.append(stripped_line)
                    prev_line = stripped_line
                
                with log_lock:
                    log_buffer.extend(processed_content)
        
        socketio.emit('logs', {'logs': get_current_logs()})
        return jsonify({'success': True, 'message': 'Logs refreshed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error refreshing logs: {str(e)}'})

@app.route('/download/outputs')
def download_outputs():
    try:
        memory_file = create_output_zip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'comfyui_outputs_{timestamp}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/civitai', methods=['POST'])
def download_civitai():
    data = request.get_json()
    url = data.get('url')
    api_key = data.get('api_key')
    model_type = data.get('model_type', 'loras')
    
    if not url:
        return jsonify({"success": False, "message": "URL is required"}), 400
    
    result = download_from_civitai(url, api_key, model_type)
    return jsonify(result)

@app.route('/download/huggingface', methods=['POST'])
def download_huggingface():
    data = request.get_json()
    url = data.get('url')
    model_type = data.get('model_type', 'loras')
    
    if not url:
        return jsonify({"success": False, "message": "URL is required"}), 400
    
    result = download_from_huggingface(url, model_type)
    return jsonify(result)

@app.route('/')
def index():
    logs = get_current_logs()
    
    # Get installed custom nodes and models
    custom_nodes = get_installed_custom_nodes()
    models = get_installed_models()
    
    # Count total models
    total_models = sum(len(models[category]) for category in models)
    
    # Detect if we're running in RunPod by checking environment variables
    is_runpod = 'RUNPOD_POD_ID' in os.environ
    
    # Get the RunPod proxy host and port
    if is_runpod:
        # In RunPod, we use the public FQDN provided by RunPod for the proxy
        # Format: https://{pod_id}-{port}.proxy.runpod.net
        pod_id = os.environ.get('RUNPOD_POD_ID', '')
        proxy_port = '8188'  # ComfyUI port
        proxy_host = f"{pod_id}-{proxy_port}.proxy.runpod.net"
        proxy_url = f"https://{proxy_host}"
    else:
        # For local development or other environments
        proxy_host = request.host.split(':')[0]
        proxy_port = '8188'
        proxy_url = f"http://{proxy_host}:{proxy_port}"
    
    response = make_response(render_template_string(HTML_TEMPLATE, 
                                                    logs=logs, 
                                                    proxy_url=proxy_url,
                                                    is_runpod=is_runpod,
                                                    custom_nodes=custom_nodes,
                                                    models=models,
                                                    total_models=total_models))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    print("Starting log monitoring thread...")
    log_thread = threading.Thread(target=tail_log_file, daemon=True)
    log_thread.start()
    
    print("Starting log viewer on port 8189...")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=8189, 
                 debug=False,
                 allow_unsafe_werkzeug=True)

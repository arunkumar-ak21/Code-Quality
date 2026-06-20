/**
 * CQ Pipeline Dashboard - Vanilla JS SPA
 */

const API_BASE = '/api/v1';

// --- API Service ---
const api = {
    async getSummary() {
        const res = await fetch(`${API_BASE}/metrics/summary`);
        if (!res.ok) throw new Error('Failed to fetch summary');
        return res.json();
    },
    async getScans(page = 1, limit = 20) {
        const res = await fetch(`${API_BASE}/scans/?page=${page}&page_size=${limit}`);
        if (!res.ok) throw new Error('Failed to fetch scans');
        return res.json();
    },
    async getScanDetail(id) {
        const res = await fetch(`${API_BASE}/scans/${id}`);
        if (!res.ok) throw new Error('Failed to fetch scan details');
        return res.json();
    }
};

// --- Utilities ---
const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('en-US', { 
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(d);
};

const getVerdictBadge = (verdict) => {
    const v = verdict.toLowerCase();
    const map = {
        'pass': { class: 'pass', icon: 'check-circle' },
        'fail': { class: 'fail', icon: 'x-circle' },
        'warn': { class: 'warn', icon: 'alert-triangle' }
    };
    const style = map[v] || { class: 'info', icon: 'info' };
    return `<span class="status-badge ${style.class}"><i data-lucide="${style.icon}" style="width:14px;height:14px;"></i> ${verdict.toUpperCase()}</span>`;
};

const getSeverityClass = (sev) => {
    return `sev-${sev.toLowerCase()}`;
};

// --- View Renderers ---

const renderLoader = () => `<div class="loader-container"><div class="spinner"></div></div>`;

const renderDashboard = async () => {
    const app = document.getElementById('router-view');
    app.innerHTML = renderLoader();
    document.getElementById('page-title').innerText = 'Overview';
    
    try {
        const [summary, recentScans] = await Promise.all([
            api.getSummary(),
            api.getScans(1, 5)
        ]);

        let html = `
            <div class="grid-3">
                <div class="glass-card metric-card">
                    <div class="metric-icon-wrap"><i data-lucide="activity" class="text-cyan"></i></div>
                    <div class="metric-info">
                        <h3>Total Scans</h3>
                        <div class="metric-value">${summary.total_scans}</div>
                    </div>
                </div>
                <div class="glass-card metric-card">
                    <div class="metric-icon-wrap"><i data-lucide="check-circle-2" class="text-emerald"></i></div>
                    <div class="metric-info">
                        <h3>Pass Rate</h3>
                        <div class="metric-value">${summary.pass_rate}%</div>
                    </div>
                </div>
                <div class="glass-card metric-card">
                    <div class="metric-icon-wrap"><i data-lucide="clock" class="text-purple"></i></div>
                    <div class="metric-info">
                        <h3>Avg Duration</h3>
                        <div class="metric-value">${summary.avg_duration}s</div>
                    </div>
                </div>
            </div>

            <div class="grid-2">
                <div class="glass-card">
                    <h3 class="mb-4">Recent Pipeline Runs</h3>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Commit</th>
                                    <th>Branch</th>
                                    <th>Verdict</th>
                                    <th>Findings</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${recentScans.scans.map(s => `
                                    <tr class="clickable-row" onclick="window.location.hash='#/scans/${s.id}'">
                                        <td class="font-mono text-cyan">${s.commit_sha.substring(0, 7)}</td>
                                        <td><i data-lucide="git-branch" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:4px;"></i>${s.branch}</td>
                                        <td>${getVerdictBadge(s.verdict)}</td>
                                        <td>${s.total_findings}</td>
                                        <td>${formatDate(s.created_at)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="glass-card">
                    <h3 class="mb-4">Top Scanners by Findings</h3>
                    <canvas id="scannersChart" height="250"></canvas>
                </div>
            </div>
        `;
        app.innerHTML = html;
        lucide.createIcons();

        // Render Chart
        if (summary.top_scanners && summary.top_scanners.length > 0) {
            const ctx = document.getElementById('scannersChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: summary.top_scanners.map(s => s.scanner),
                    datasets: [{
                        data: summary.top_scanners.map(s => s.count),
                        backgroundColor: ['#00E5FF', '#B000FF', '#00E676', '#FFC400', '#FF1744'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    cutout: '75%',
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94A3B8' } }
                    }
                }
            });
        }

    } catch (err) {
        app.innerHTML = `<div class="glass-card"><p class="text-rose"><i data-lucide="alert-circle"></i> Error loading dashboard: ${err.message}</p></div>`;
        lucide.createIcons();
    }
};

const renderScansList = async () => {
    const app = document.getElementById('router-view');
    app.innerHTML = renderLoader();
    document.getElementById('page-title').innerText = 'Scan History';

    try {
        const data = await api.getScans(1, 50); // Fetch up to 50 for now
        
        let html = `
            <div class="glass-card">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Commit</th>
                                <th>Branch</th>
                                <th>Author</th>
                                <th>Verdict</th>
                                <th>Findings</th>
                                <th>Duration</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.scans.map(s => `
                                <tr class="clickable-row" onclick="window.location.hash='#/scans/${s.id}'">
                                    <td class="font-mono text-cyan">${s.commit_sha.substring(0, 7)}</td>
                                    <td><i data-lucide="git-branch" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:4px;"></i>${s.branch}</td>
                                    <td>${s.author}</td>
                                    <td>${getVerdictBadge(s.verdict)}</td>
                                    <td>
                                        <div class="flex gap-2">
                                            ${s.critical_count > 0 ? `<span class="sev-critical font-bold">${s.critical_count}C</span>` : ''}
                                            ${s.high_count > 0 ? `<span class="sev-high font-bold">${s.high_count}H</span>` : ''}
                                            <span class="text-muted">${s.total_findings} Total</span>
                                        </div>
                                    </td>
                                    <td>${s.duration_seconds.toFixed(1)}s</td>
                                    <td>${formatDate(s.created_at)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        app.innerHTML = html;
        lucide.createIcons();
    } catch (err) {
        app.innerHTML = `<div class="glass-card"><p class="text-rose">Error loading scans: ${err.message}</p></div>`;
    }
};

const renderScanDetail = async (id) => {
    const app = document.getElementById('router-view');
    app.innerHTML = renderLoader();
    document.getElementById('page-title').innerText = 'Scan Detail';

    try {
        const scan = await api.getScanDetail(id);
        
        let html = `
            <div class="mb-6 flex gap-4">
                <a href="#/scans" class="btn"><i data-lucide="arrow-left"></i> Back to Scans</a>
            </div>
            
            <div class="glass-card mb-6 flex" style="justify-content: space-between; align-items: center;">
                <div>
                    <h2 class="mb-4">Commit <span class="font-mono text-cyan">${scan.commit_sha}</span></h2>
                    <div class="flex gap-4 text-secondary">
                        <span><i data-lucide="git-branch" style="width:16px;height:16px;"></i> ${scan.branch}</span>
                        <span><i data-lucide="user" style="width:16px;height:16px;"></i> ${scan.author}</span>
                        <span><i data-lucide="clock" style="width:16px;height:16px;"></i> ${formatDate(scan.created_at)}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="transform: scale(1.5); transform-origin: right;">${getVerdictBadge(scan.verdict)}</div>
                    <div class="mt-6 text-muted">Scanned ${scan.files_scanned} files in ${scan.duration_seconds.toFixed(1)}s</div>
                </div>
            </div>

            <div class="grid-3">
                <div class="glass-card" style="text-align:center; padding: 16px;">
                    <h4 class="text-rose mb-2">Critical</h4>
                    <div class="metric-value sev-critical">${scan.critical_count}</div>
                </div>
                <div class="glass-card" style="text-align:center; padding: 16px;">
                    <h4 class="text-rose mb-2" style="color: #FF5252">High</h4>
                    <div class="metric-value sev-high">${scan.high_count}</div>
                </div>
                <div class="glass-card" style="text-align:center; padding: 16px;">
                    <h4 class="text-amber mb-2" style="color: #FFC400">Medium</h4>
                    <div class="metric-value sev-medium">${scan.medium_count}</div>
                </div>
            </div>

            <h3 class="mb-4 mt-6">Findings (${scan.findings.length})</h3>
            ${scan.findings.length === 0 ? '<div class="glass-card"><p class="text-emerald"><i data-lucide="check-circle"></i> No issues found in this scan! Great job.</p></div>' : ''}
            
            <div class="findings-list">
                ${scan.findings.map(f => `
                    <div class="finding-item">
                        <div class="finding-header">
                            <div>
                                <div class="finding-title mb-2">
                                    <span class="${getSeverityClass(f.severity)} font-bold">[${f.severity.toUpperCase()}]</span> 
                                    ${f.title}
                                </div>
                                <div class="finding-meta">
                                    <span><i data-lucide="file-code" style="width:14px;height:14px;"></i> ${f.file_path}:${f.line_number}</span>
                                    <span><i data-lucide="cpu" style="width:14px;height:14px;"></i> ${f.scanner}</span>
                                    ${f.cve_id ? `<span class="text-rose"><i data-lucide="shield-alert" style="width:14px;height:14px;"></i> ${f.cve_id}</span>` : ''}
                                </div>
                            </div>
                        </div>
                        <p class="text-secondary">${f.message}</p>
                        ${f.code_snippet ? `
                            <div class="finding-code font-mono">
                                <pre>${f.code_snippet.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                            </div>
                        ` : ''}
                        ${f.suggestion ? `<p class="mt-6 text-emerald"><i data-lucide="lightbulb" style="width:16px;height:16px;"></i> <b>Suggestion:</b> ${f.suggestion}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
        app.innerHTML = html;
        lucide.createIcons();
    } catch (err) {
        app.innerHTML = `<div class="glass-card"><p class="text-rose">Error loading scan details: ${err.message}</p></div>`;
    }
};

// --- Router ---
const router = () => {
    const hash = window.location.hash || '#/';
    
    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
    if (hash.startsWith('#/scans')) {
        document.getElementById('nav-scans')?.classList.add('active');
    } else {
        document.getElementById('nav-dashboard')?.classList.add('active');
    }

    // Route matching
    if (hash === '#/') {
        renderDashboard();
    } else if (hash === '#/scans') {
        renderScansList();
    } else if (hash.startsWith('#/scans/')) {
        const id = hash.split('/')[2];
        renderScanDetail(id);
    } else {
        renderDashboard();
    }
};

// Initialize
window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);

document.addEventListener('DOMContentLoaded', () => {
    const feedElement = document.getElementById('transaction-feed');
    const logElement = document.getElementById('risk-log');

    // ──────────────────────────────────────────────
    // Tab Navigation
    // ──────────────────────────────────────────────
    const navLinks = document.querySelectorAll('.nav-link');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active class from all links and panes
            navLinks.forEach(l => l.classList.remove('active'));
            tabPanes.forEach(p => p.style.display = 'none');
            
            // Add active class to clicked link and show target pane
            link.classList.add('active');
            const targetId = link.getAttribute('data-target');
            if (targetId) {
                const targetPane = document.getElementById(targetId);
                if (targetPane) {
                    targetPane.style.display = 'block';
                }
            }
        });
    });

    // ──────────────────────────────────────────────
    // Inner Docs Navigation
    // ──────────────────────────────────────────────
    const docLinks = document.querySelectorAll('.docs-nav-link');
    const docSections = document.querySelectorAll('.doc-section');

    docLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Update active link
            docLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // Switch content section
            const targetId = link.getAttribute('data-doc');
            docSections.forEach(sec => {
                if (sec.id === targetId) {
                    sec.classList.add('active');
                } else {
                    sec.classList.remove('active');
                }
            });
        });
    });

    // ──────────────────────────────────────────────
    // Fetch live data from the Risk API
    // ──────────────────────────────────────────────

    async function fetchTransactions() {
        try {
            const res = await fetch('/api/transactions');
            if (!res.ok) return;
            const data = await res.json();
            
            feedElement.innerHTML = '';
            
            if (data.length === 0) {
                feedElement.innerHTML = `
                    <tr>
                        <td colspan="4" class="muted" style="padding: 24px 16px; text-align: center;">
                            No transactions yet. Send a request to <strong>/v1/risk/evaluate</strong> or <strong>/webhooks/razorpay</strong> to see decisions here.
                        </td>
                    </tr>
                `;
                return;
            }
            
            data.forEach(tx => {
                const row = document.createElement('tr');
                
                let badgeClass = 'badge-release';
                if (tx.decision === 'HOLD') badgeClass = 'badge-hold';
                if (tx.decision === 'REFUSE') badgeClass = 'badge-refuse';

                const amount = typeof tx.amount === 'number' 
                    ? `₹ ${tx.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` 
                    : tx.amount;
                
                const pid = tx.payment_id.length > 16 
                    ? tx.payment_id.substring(0, 16) + '...' 
                    : tx.payment_id;

                row.innerHTML = `
                    <td><strong>${pid}</strong></td>
                    <td class="muted">${tx.source}</td>
                    <td>${amount}</td>
                    <td><span class="badge ${badgeClass}">${tx.decision}</span></td>
                `;
                feedElement.appendChild(row);
            });
        } catch (e) {
            console.warn('Failed to fetch transactions:', e);
        }
    }

    async function fetchRiskLog() {
        try {
            const res = await fetch('/api/risk-log');
            if (!res.ok) return;
            const data = await res.json();
            
            logElement.innerHTML = '';
            
            if (data.length === 0) {
                logElement.innerHTML = `
                    <div class="log-entry" style="padding: 24px 16px;">
                        <span class="muted">Waiting for engine activity...</span>
                    </div>
                `;
                return;
            }
            
            data.forEach(log => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                
                // Highlight engine names
                let formattedMsg = log.msg
                    .replace('[Conformal Engine]', '<strong style="color: #000;">[Conformal Engine]</strong>')
                    .replace('[Semantic Engine]', '<strong style="color: var(--alert-color);">[Semantic Engine]</strong>')
                    .replace('[Decision Router]', '<strong style="color: var(--hold-color);">[Decision Router]</strong>');

                // Highlight decisions
                formattedMsg = formattedMsg
                    .replace('→ RELEASE', '→ <span style="color: var(--success-color); font-weight: 500;">RELEASE</span>')
                    .replace('→ REFUSE', '→ <span style="color: var(--alert-color); font-weight: 500;">REFUSE</span>')
                    .replace('→ HOLD', '→ <span style="color: var(--hold-color); font-weight: 500;">HOLD</span>');

                entry.innerHTML = `
                    <span class="log-time">${log.time}</span>
                    <span>${formattedMsg}</span>
                `;
                logElement.appendChild(entry);
            });
        } catch (e) {
            console.warn('Failed to fetch risk log:', e);
        }
    }

    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            if (!res.ok) return;
            const data = await res.json();
            
            // Update stat cards
            const statValues = document.querySelectorAll('.stat-value');
            if (statValues[0]) statValues[0].textContent = data.total_transactions.toLocaleString();
            if (statValues[1]) statValues[1].textContent = data.agents_checked.toLocaleString();
            if (statValues[2]) statValues[2].textContent = data.escrow_holds.toLocaleString();
            if (statValues[3]) {
                statValues[3].textContent = `₹ ${data.fraud_prevented.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            }
        } catch (e) {
            console.warn('Failed to fetch stats:', e);
        }
    }

    // ──────────────────────────────────────────────
    // Day 3 APIs (Transactions, Risk, Settings Tabs)
    // ──────────────────────────────────────────────
    
    window.loadTransactionsTab = async function() {
        const feed = document.getElementById('full-transaction-feed');
        if (!feed) return;
        
        const filter = document.getElementById('txn-filter') ? document.getElementById('txn-filter').value : 'all';
        
        try {
            const res = await fetch('/api/transactions');
            if (!res.ok) return;
            let data = await res.json();
            
            if (filter !== 'all') {
                data = data.filter(tx => tx.decision === filter);
            }
            
            feed.innerHTML = '';
            if (data.length === 0) {
                feed.innerHTML = `<tr><td colspan="6" class="muted" style="text-align: center; padding: 24px;">No transactions found.</td></tr>`;
                return;
            }
            
            data.forEach(tx => {
                const row = document.createElement('tr');
                let badgeClass = 'badge-release';
                if (tx.decision === 'HOLD') badgeClass = 'badge-hold';
                if (tx.decision === 'REFUSE') badgeClass = 'badge-refuse';
                
                const amount = typeof tx.amount === 'number' 
                    ? `₹ ${tx.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` 
                    : tx.amount;
                
                row.innerHTML = `
                    <td><code>${tx.audit_id.substring(0,8)}</code></td>
                    <td><strong>${tx.payment_id}</strong></td>
                    <td class="muted">${tx.source}</td>
                    <td>${amount}</td>
                    <td><span class="badge ${badgeClass}">${tx.decision}</span></td>
                    <td class="muted" style="font-size: 0.8rem;">${tx.reason_codes.join(', ')}</td>
                `;
                feed.appendChild(row);
            });
        } catch (e) {
            console.error('Failed to load transactions tab', e);
        }
    };
    
    window.loadEvaluation = async function() {
        const grid = document.getElementById('eval-metrics-grid');
        const content = document.getElementById('eval-report-content');
        if (!grid || !content) return;
        
        try {
            const res = await fetch('/api/evaluation');
            if (!res.ok) return;
            const data = await res.json();
            
            if (data.error) {
                content.innerHTML = `<p class="alert-text">${data.error}</p>`;
                return;
            }
            
            grid.innerHTML = `
                <div class="stat-card">
                    <h3 class="stat-label">Coverage</h3>
                    <p class="stat-value" style="color: var(--primary-color);">${data.metrics.conformal_coverage}</p>
                </div>
                <div class="stat-card">
                    <h3 class="stat-label">Precision</h3>
                    <p class="stat-value">${data.metrics.precision}</p>
                </div>
                <div class="stat-card">
                    <h3 class="stat-label">Recall</h3>
                    <p class="stat-value">${data.metrics.recall}</p>
                </div>
                <div class="stat-card">
                    <h3 class="stat-label">False Positive Cost</h3>
                    <p class="stat-value alert-text">${data.metrics.false_positive_cost_est}</p>
                </div>
            `;
            
            content.innerHTML = `
                <table class="data-table">
                    <tr><td width="30%"><strong>Dataset</strong></td><td>${data.dataset}</td></tr>
                    <tr><td><strong>Model Type</strong></td><td>${data.model_type}</td></tr>
                    <tr><td><strong>Evaluated Transactions</strong></td><td>${data.transactions_evaluated.toLocaleString()}</td></tr>
                    <tr><td><strong>F1 Score</strong></td><td>${data.metrics.f1_score}</td></tr>
                    <tr><td><strong>AUCPR</strong></td><td>${data.metrics.aucpr}</td></tr>
                </table>
            `;
        } catch(e) {
            console.error('Failed to load evaluation report', e);
        }
    };
    
    async function loadConfig() {
        const el = document.getElementById('config-json');
        if (!el) return;
        try {
            const res = await fetch('/api/config');
            if (!res.ok) return;
            const data = await res.json();
            el.textContent = JSON.stringify(data, null, 4);
        } catch(e) {
            console.error('Failed to load config', e);
        }
    }

    // ──────────────────────────────────────────────
    // Initial load + auto-refresh every 5 seconds
    // ──────────────────────────────────────────────

    function refreshAll() {
        fetchTransactions();
        fetchRiskLog();
        fetchStats();
        
        // Also refresh tabs if they are active
        if (document.getElementById('tab-transactions').style.display !== 'none') {
            loadTransactionsTab();
        }
        if (document.getElementById('tab-settings').style.display !== 'none') {
            loadConfig();
        }
    }

    refreshAll();
    // Only load evaluation on demand or if tab is active, since it reads disk
    document.querySelector('[data-target="tab-risk"]').addEventListener('click', loadEvaluation);
    document.querySelector('[data-target="tab-settings"]').addEventListener('click', loadConfig);
    document.querySelector('[data-target="tab-transactions"]').addEventListener('click', loadTransactionsTab);

    setInterval(refreshAll, 5000);

    // Refresh Data button handler
    const refreshBtn = document.querySelector('.btn-primary');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshAll();
            refreshBtn.textContent = 'Refreshing...';
            setTimeout(() => { refreshBtn.textContent = 'Refresh Data'; }, 800);
        });
    }
});

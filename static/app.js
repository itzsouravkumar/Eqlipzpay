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
    // Initial load + auto-refresh every 5 seconds
    // ──────────────────────────────────────────────

    function refreshAll() {
        fetchTransactions();
        fetchRiskLog();
        fetchStats();
    }

    refreshAll();
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

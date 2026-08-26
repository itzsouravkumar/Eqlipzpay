document.addEventListener('DOMContentLoaded', () => {
    // Mock Data for the Transactions Feed
    const transactions = [
        { id: 'pay_H3J92Ksl2', source: 'AGENT_MCP', amount: '₹ 450.00', decision: 'RELEASE' },
        { id: 'pay_K9L83Mnp1', source: 'HUMAN', amount: '₹ 1,200.00', decision: 'RELEASE' },
        { id: 'pay_X2Y45Zqa9', source: 'AGENT_AP2', amount: '₹ 8,900.00', decision: 'HOLD' },
        { id: 'pay_V1B34Nmc8', source: 'HUMAN', amount: '₹ 42,500.00', decision: 'REFUSE' },
        { id: 'pay_Q8W76Ert5', source: 'AGENT_UCP', amount: '₹ 120.00', decision: 'RELEASE' }
    ];

    // Mock Data for the Risk Log
    const logs = [
        { time: '10:42:15 AM', msg: '[Conformal Engine] pay_Q8W... set: {benign} | conf: 0.98 -> RELEASE' },
        { time: '10:41:02 AM', msg: '[Semantic Engine] pay_V1B... CART MISMATCH DETECTED' },
        { time: '10:41:01 AM', msg: '[Conformal Engine] pay_V1B... set: {fraud} | conf: 0.85 -> REFUSE' },
        { time: '10:35:22 AM', msg: '[Decision Router] pay_X2Y... set: {benign, fraud} -> HOLD (48h)' },
        { time: '10:35:20 AM', msg: '[Conformal Engine] pay_X2Y... set: {benign, fraud} | conf: 0.52' }
    ];

    const feedElement = document.getElementById('transaction-feed');
    const logElement = document.getElementById('risk-log');

    // Populate Transactions
    transactions.forEach(tx => {
        const row = document.createElement('tr');
        
        let badgeClass = 'badge-release';
        if (tx.decision === 'HOLD') badgeClass = 'badge-hold';
        if (tx.decision === 'REFUSE') badgeClass = 'badge-refuse';

        row.innerHTML = `
            <td><strong>${tx.id}</strong></td>
            <td class="muted">${tx.source}</td>
            <td>${tx.amount}</td>
            <td><span class="badge ${badgeClass}">${tx.decision}</span></td>
        `;
        feedElement.appendChild(row);
    });

    // Populate Logs
    logs.forEach(log => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        
        // Highlight engine names
        let formattedMsg = log.msg.replace('[Conformal Engine]', '<strong style="color: #000;">[Conformal Engine]</strong>');
        formattedMsg = formattedMsg.replace('[Semantic Engine]', '<strong style="color: var(--alert-color);">[Semantic Engine]</strong>');
        formattedMsg = formattedMsg.replace('[Decision Router]', '<strong style="color: var(--hold-color);">[Decision Router]</strong>');

        entry.innerHTML = `
            <span class="log-time">${log.time}</span>
            <span>${formattedMsg}</span>
        `;
        logElement.appendChild(entry);
    });
});

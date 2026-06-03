// Global State
let currentData = null;
let deskOverrides = {};

const formatNumber = (num) => {
    if (num === null || num === undefined) return '--';
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toFixed(2);
};

// Web Components
class FrtbDeskTable extends HTMLElement {
    constructor() {
        super();
        this.desks = [];
    }

    set data(desks) {
        this.desks = desks;
        this.render();
    }

    render() {
        let html = `
            <table class="dense-table">
                <thead>
                    <tr>
                        <th>Desk ID</th>
                        <th>Eligibility</th>
                        <th>IMCC 60d</th>
                        <th>SES 60d</th>
                        <th>Multiplier</th>
                        <th>PLA Addon</th>
                        <th>Models Based Cap.</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        this.desks.forEach((desk, idx) => {
            const eligClass = desk.desk_eligibility === 'IMA_ELIGIBLE' ? 'status-green' : 'status-amber';
            const plaClass = desk.capital.pla_addon > 0 ? 'status-amber' : '';
            html += `
                <tr data-index="${idx}" style="cursor: pointer;">
                    <td><strong>${desk.desk_id}</strong></td>
                    <td class="${eligClass}">${desk.desk_eligibility}</td>
                    <td class="numeric">${formatNumber(desk.capital.imcc_60d_avg)}</td>
                    <td class="numeric">${formatNumber(desk.capital.ses_60d_avg)}</td>
                    <td class="numeric">${desk.capital.multiplier.toFixed(2)}</td>
                    <td class="numeric ${plaClass}">${formatNumber(desk.capital.pla_addon)}</td>
                    <td class="numeric status-green">${formatNumber(desk.capital.models_based_capital)}</td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
        this.innerHTML = html;

        // Attach event listeners after render
        this.querySelectorAll('tbody tr').forEach(row => {
            row.addEventListener('click', (e) => {
                this.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
                e.currentTarget.classList.add('selected');
                const idx = e.currentTarget.getAttribute('data-index');
                const event = new CustomEvent('desk-selected', { detail: this.desks[idx] });
                this.dispatchEvent(event);
            });
        });
        
        // Auto-select first row if exists
        if (this.desks.length > 0) {
            this.querySelector('tbody tr').click();
        }
    }
}
customElements.define('frtb-desk-table', FrtbDeskTable);

// UI Initialization
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    document.getElementById('recalculate-btn').addEventListener('click', fetchData);
    fetchData();
});

function setupTabs() {
    const links = document.querySelectorAll('.nav-links li');
    links.forEach(link => {
        link.addEventListener('click', () => {
            links.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            const targetId = link.getAttribute('data-tab');
            document.getElementById(targetId).classList.add('active');
        });
    });
}

async function fetchData() {
    try {
        const response = await fetch('/api/capital-run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ima_desk_eligibility: deskOverrides })
        });
        currentData = await response.json();
        renderAll();
    } catch (e) {
        console.error("Error fetching capital run:", e);
    }
}

function renderAll() {
    if (!currentData) return;
    
    // Global Header
    const sa = currentData.orchestration;
    const ima = currentData.ima;
    document.getElementById('ctx-date').textContent = `Date: ${sa.calculation_date}`;
    document.getElementById('ctx-currency').textContent = `CCY: ${sa.base_currency}`;
    document.getElementById('ctx-regime').textContent = `Regime: ${sa.jurisdiction_family}`;
    document.getElementById('ctx-run-id').textContent = `Run ID: ${sa.run_id}`;
    
    const totalCap = sa.total_capital + ima.total_market_risk_capital;
    document.getElementById('global-total-capital').textContent = formatNumber(totalCap);

    renderOrchestrationTab();
    renderSbmTab();
    renderDrcTab();
    renderImaTab();
}

// TAB 1: Orchestration
function renderOrchestrationTab() {
    const sa = currentData.orchestration;
    const ima = currentData.ima;
    
    // SA Subtotals
    const saTbody = document.querySelector('#sa-subtotals-table tbody');
    saTbody.innerHTML = '';
    sa.component_subtotals.forEach(sub => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${sub.component}</strong></td>
            <td>${sub.package_name}</td>
            <td class="numeric">${sub.subtotal_count}</td>
            <td class="numeric">${formatNumber(sub.total_capital)}</td>
        `;
        saTbody.appendChild(tr);
    });

    // Desk Routing
    const routingTbody = document.querySelector('#ima-routing-table tbody');
    routingTbody.innerHTML = '';
    ima.desk_records.forEach(desk => {
        const isFallback = desk.desk_eligibility === 'SA_FALLBACK';
        const colorClass = isFallback ? 'status-amber' : 'status-green';
        const btnText = isFallback ? 'Restore IMA' : 'Force SA Fallback';
        
        const tr = document.createElement('tr');
        if(isFallback) tr.classList.add('bg-amber');
        tr.innerHTML = `
            <td><strong>${desk.desk_id}</strong></td>
            <td class="${colorClass}">${desk.desk_eligibility}</td>
            <td class="numeric">${formatNumber(desk.capital.models_based_capital)}</td>
            <td><button class="action-btn" onclick="toggleDeskEligibility('${desk.desk_id}', '${isFallback}')">${btnText}</button></td>
        `;
        routingTbody.appendChild(tr);
    });
}

window.toggleDeskEligibility = function(deskId, currentlyFallback) {
    deskOverrides[deskId] = (currentlyFallback === 'true') ? 'IMA_ELIGIBLE' : 'SA_FALLBACK';
    fetchData();
}

// TAB 2: SBM
function renderSbmTab() {
    const sbm = currentData.components.sbm;
    const tbody = document.querySelector('#sbm-risk-classes-table tbody');
    tbody.innerHTML = '';
    
    sbm.risk_classes.forEach((rc, idx) => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.innerHTML = `
            <td><strong>${rc.risk_class}</strong></td>
            <td>${rc.risk_measure}</td>
            <td class="numeric status-green">${formatNumber(rc.selected_capital)}</td>
            <td class="numeric ${rc.selected_scenario==='LOW'?'status-green':''}">${formatNumber(rc.scenario_totals.LOW)}</td>
            <td class="numeric ${rc.selected_scenario==='MEDIUM'?'status-green':''}">${formatNumber(rc.scenario_totals.MEDIUM)}</td>
            <td class="numeric ${rc.selected_scenario==='HIGH'?'status-green':''}">${formatNumber(rc.scenario_totals.HIGH)}</td>
        `;
        tr.addEventListener('click', () => {
            document.querySelectorAll('#sbm-risk-classes-table tr').forEach(r => r.classList.remove('selected'));
            tr.classList.add('selected');
            renderSbmBuckets(rc.buckets);
        });
        tbody.appendChild(tr);
        if (idx === 0) tr.click(); // Auto-select first
    });
}

function renderSbmBuckets(buckets) {
    const container = document.getElementById('sbm-buckets-container');
    container.innerHTML = '';
    
    buckets.forEach(b => {
        const table = document.createElement('table');
        table.className = 'dense-table';
        table.style.marginBottom = '12px';
        
        const floorWarning = b.floor_applied ? '<span class="status-amber"> [FLOOR]</span>' : '';
        
        let html = `
            <thead>
                <tr>
                    <th colspan="4">Bucket: ${b.bucket_id} | Kb: ${formatNumber(b.kb)}${floorWarning}</th>
                </tr>
                <tr>
                    <th>Sensitivity ID</th>
                    <th class="numeric">Raw Amount</th>
                    <th class="numeric">Risk Weight</th>
                    <th class="numeric">Scaled Amount</th>
                </tr>
            </thead>
            <tbody>
        `;
        b.weighted_sensitivities.forEach(s => {
            html += `
                <tr>
                    <td class="indent-1">${s.sensitivity_id}</td>
                    <td class="numeric">${formatNumber(s.raw_amount)}</td>
                    <td class="numeric">${s.risk_weight.toFixed(4)}</td>
                    <td class="numeric">${formatNumber(s.scaled_amount)}</td>
                </tr>
            `;
        });
        html += `</tbody>`;
        table.innerHTML = html;
        container.appendChild(table);
    });
}

// TAB 3: DRC
function renderDrcTab() {
    const drc = currentData.components.drc;
    
    // Attribution
    const attrTbody = document.querySelector('#drc-attribution-table tbody');
    attrTbody.innerHTML = '';
    drc.attribution_records.forEach(att => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${att.source_id}</td>
            <td>${att.source_level}</td>
            <td class="numeric">${formatNumber(att.contribution)}</td>
        `;
        attrTbody.appendChild(tr);
    });
    
    // Tree
    const tree = document.getElementById('drc-tree-container');
    tree.innerHTML = '';
    
    drc.categories.forEach(cat => {
        const catDiv = document.createElement('div');
        catDiv.innerHTML = `<strong>Category: ${cat.risk_class}</strong> - Capital: ${formatNumber(cat.capital)}`;
        catDiv.style.padding = '4px';
        catDiv.style.backgroundColor = 'var(--bg-header)';
        catDiv.style.borderBottom = '1px solid var(--border-color)';
        tree.appendChild(catDiv);
        
        cat.bucket_results.forEach(b => {
            const table = document.createElement('table');
            table.className = 'dense-table';
            table.style.marginBottom = '8px';
            let html = `
                <thead>
                    <tr>
                        <th class="indent-1" colspan="4">Bucket: ${b.bucket_key} | Cap: ${formatNumber(b.capital)} | HBR: ${b.hbr.ratio.toFixed(2)}</th>
                    </tr>
                    <tr>
                        <th class="indent-2">Obligor</th>
                        <th>Seniority</th>
                        <th class="numeric">Net Amount</th>
                        <th>Direction</th>
                    </tr>
                </thead>
                <tbody>
            `;
            
            // Find net jtds for this bucket
            const netJtds = drc.net_jtds.filter(j => b.net_jtd_ids.includes(j.net_jtd_id));
            netJtds.forEach(j => {
                html += `
                    <tr>
                        <td class="indent-2">${j.obligor_or_tranche_key}</td>
                        <td>${j.seniority_layer}</td>
                        <td class="numeric">${formatNumber(j.net_amount)}</td>
                        <td class="${j.net_direction==='SHORT'?'status-red':''}">${j.net_direction}</td>
                    </tr>
                `;
            });
            html += `</tbody>`;
            table.innerHTML = html;
            tree.appendChild(table);
        });
    });
}

// TAB 4: IMA
function renderImaTab() {
    const ima = currentData.ima;
    const deskTable = document.getElementById('ima-desk-summary');
    
    // Listen for the custom event from our Web Component
    if (!deskTable.hasAttribute('listener-attached')) {
        deskTable.addEventListener('desk-selected', (e) => {
            renderImaDetails(e.detail);
        });
        deskTable.setAttribute('listener-attached', 'true');
    }

    // Pass the raw data object down to the component
    deskTable.data = ima.desk_records;
}

function renderImaDetails(desk) {
    // IMCC / SES
    const imccDiv = document.getElementById('ima-imcc-ses-details');
    imccDiv.innerHTML = `
        <table class="dense-table" style="margin-bottom:8px;">
            <thead><tr><th colspan="2">IMCC Result</th></tr></thead>
            <tbody>
                <tr><td>Unconstrained ES</td><td class="numeric">${formatNumber(desk.imcc.unconstrained.lha_es)}</td></tr>
                <tr><td>Constrained ES</td><td class="numeric">${formatNumber(desk.imcc.constrained_lha_es)}</td></tr>
                <tr><td>Total IMCC</td><td class="numeric status-green">${formatNumber(desk.imcc.imcc)}</td></tr>
            </tbody>
        </table>
        <table class="dense-table">
            <thead><tr><th colspan="2">SES Aggregation Result</th></tr></thead>
            <tbody>
                <tr><td>Type A Count</td><td class="numeric">${desk.ses.type_a_count}</td></tr>
                <tr><td>Type B Count</td><td class="numeric">${desk.ses.type_b_count}</td></tr>
                <tr><td>Total SES</td><td class="numeric status-green">${formatNumber(desk.ses.total_ses)}</td></tr>
            </tbody>
        </table>
    `;
    
    // Backtest / PLA
    const btDiv = document.getElementById('ima-backtest-details');
    const bLevel = desk.backtesting.levels[0];
    const pZoneColor = desk.pla.zone === 'GREEN' ? 'status-green' : (desk.pla.zone === 'AMBER' ? 'status-amber' : 'status-red');
    
    btDiv.innerHTML = `
        <table class="dense-table" style="margin-bottom:8px;">
            <thead><tr><th colspan="4">Backtesting (Window: ${desk.backtesting.window_size})</th></tr></thead>
            <tbody>
                <tr>
                    <td>99% VaR</td>
                    <td>APL Ex: <span class="${bLevel.apl_exceptions>bLevel.exception_limit?'status-red':'status-green'}">${bLevel.apl_exceptions}</span></td>
                    <td>HPL Ex: <span class="${bLevel.hpl_exceptions>bLevel.exception_limit?'status-red':'status-green'}">${bLevel.hpl_exceptions}</span></td>
                    <td class="${bLevel.level_passed?'status-green':'status-red'}">${bLevel.level_passed?'PASS':'FAIL'}</td>
                </tr>
            </tbody>
        </table>
        <table class="dense-table">
            <thead><tr><th colspan="2">P&L Attribution</th></tr></thead>
            <tbody>
                <tr><td>KS Statistic</td><td class="numeric">${desk.pla.ks_statistic.toFixed(4)}</td></tr>
                <tr><td>Zone</td><td class="${pZoneColor}"><strong>${desk.pla.zone}</strong></td></tr>
            </tbody>
        </table>
    `;
}

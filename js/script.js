console.log("Script loaded. Version: Heartbeat Enabled");

// --- HEARTBEAT LOGIC ---
// Pings the local server every 1s. If this stops, the server shuts down.
setInterval(() => {
    fetch('/heartbeat', { method: 'POST' }).catch(() => {
        // Ignore errors (e.g. if server is already down)
    });
}, 1000);

// --- SAFETY CHECK ---
if (typeof Chart === 'undefined') {
    const msg = "Chart.js not loaded. Please ensure 'js/chart.js' exists and is a valid UMD build.";
    alert(msg);
    console.error(msg);
}

// --- CONSTANTS ---
const CURR_YEAR = new Date().getFullYear();
const DEFAULT_START = `${CURR_YEAR}-01-01`;
const DEFAULT_END = `${CURR_YEAR}-12-31`;

const DEFAULT_CONFIG = [
    {name: "Wake up", type: "time", weight: 20, target: "06:00", condition: "before", days: "Mon,Tue,Wed,Thu,Fri,Sat,Sun", startDate: DEFAULT_START, endDate: DEFAULT_END},
{name: "Gym", type: "bool", weight: 20, days: "Mon,Tue,Wed,Thu,Fri", startDate: DEFAULT_START, endDate: DEFAULT_END},
{name: "Deep Work", type: "bool", weight: 20, days: "Mon,Tue,Wed,Thu,Fri", startDate: DEFAULT_START, endDate: DEFAULT_END},
{name: "Reading", type: "bool", weight: 20, days: "Mon,Tue,Wed,Thu,Fri,Sat,Sun", startDate: DEFAULT_START, endDate: DEFAULT_END},
{name: "Sleep", type: "time", weight: 20, target: "23:00", condition: "before", days: "Mon,Tue,Wed,Thu,Fri,Sat,Sun", startDate: DEFAULT_START, endDate: DEFAULT_END}
];

// --- STATE INITIALIZATION & MIGRATION ---
let appData = {};
let appConfig = [];

// Migration: Ensure all tasks have dates
const migrateConfig = (cfg) => {
    return cfg.map(t => ({
        ...t,
        startDate: t.startDate || DEFAULT_START,
        endDate: t.endDate || DEFAULT_END
    }));
};

let currentMonday = getMonday(new Date());
let chartRefs = { score: null, time: null };

// --- DOM ELEMENTS ---
const modal = document.getElementById('configModal');
const form = document.getElementById('taskForm');
const inpType = document.getElementById('inpType');
const radioRepeat = document.getElementById('radioRepeat');
const radioOnce = document.getElementById('radioOnce');

// --- EVENT LISTENERS ---
document.addEventListener('DOMContentLoaded', init);
if(document.getElementById('btnPrev')) document.getElementById('btnPrev').addEventListener('click', () => changeWeek(-7));
if(document.getElementById('btnNext')) document.getElementById('btnNext').addEventListener('click', () => changeWeek(7));
if(document.getElementById('btnManage')) document.getElementById('btnManage').addEventListener('click', openModal);
if(document.getElementById('btnAdd')) document.getElementById('btnAdd').addEventListener('click', showAddForm);
if(document.getElementById('btnCancelForm')) document.getElementById('btnCancelForm').addEventListener('click', hideForm);
if(document.getElementById('btnSaveTask')) document.getElementById('btnSaveTask').addEventListener('click', saveTaskFromForm);
if(document.getElementById('btnCloseModal')) document.getElementById('btnCloseModal').addEventListener('click', closeModal);
if(document.getElementById('btnAllDays')) document.getElementById('btnAllDays').addEventListener('click', selectAllDays);
if(inpType) inpType.addEventListener('change', toggleFormInputs);
if(radioRepeat) radioRepeat.addEventListener('change', toggleFreqInputs);
if(radioOnce) radioOnce.addEventListener('change', toggleFreqInputs);

// --- PLUGIN DEFINITION ---
const sleepConnectorPlugin = {
    id: 'sleepConnector',
    afterDatasetsDraw(chart) {
        if (!chart.chartArea || !chart.scales.x || !chart.scales.y) return;
        const { ctx, chartArea: { left, right }, scales: { x, y } } = chart;

        try {
            const metaWake = chart.getDatasetMeta(0);
            const metaSleep = chart.getDatasetMeta(1);
            if (!metaWake || !metaSleep || metaWake.hidden || metaSleep.hidden) return;

            const wakeData = chart.data.datasets[0].data;
            const sleepData = chart.data.datasets[1].data;

            ctx.save();
            ctx.setLineDash([5, 5]);
            ctx.lineWidth = 2;
            ctx.font = 'bold 11px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            for (let i = 0; i < sleepData.length - 1; i++) {
                const sleepVal = sleepData[i];
                const wakeValNextDay = wakeData[i+1];

                if (sleepVal != null && wakeValNextDay != null) {
                    const modelSleep = metaSleep.data[i];
                    const modelWakeNext = metaWake.data[i+1];

                    if (modelSleep && modelWakeNext && !modelSleep.skip && !modelWakeNext.skip) {
                        ctx.beginPath();
                        ctx.strokeStyle = '#facc15';
                        ctx.moveTo(modelSleep.x, modelSleep.y);
                        ctx.lineTo(modelWakeNext.x, modelWakeNext.y);
                        ctx.stroke();

                        const midX = (modelSleep.x + modelWakeNext.x) / 2;
                        if (midX >= left && midX <= right) {
                            let duration = 0;
                            let sVal = sleepVal;
                            if (sVal >= 24) sVal -= 24;
                            let wVal = wakeValNextDay;

                            if (wVal < sVal) duration = (24 - sVal) + wVal;
                            else duration = wVal - sVal;
                            if (duration < 0) duration += 24;

                            const text = `${duration.toFixed(1)}h`;
                            const textWidth = ctx.measureText(text).width;
                            const midY = (modelSleep.y + modelWakeNext.y) / 2;

                            ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
                            ctx.fillRect(midX - textWidth/2 - 4, midY - 8, textWidth + 8, 16);
                            ctx.fillStyle = '#facc15';
                            ctx.fillText(text, midX, midY);
                        }
                    }
                }
            }
            ctx.restore();
        } catch (e) { console.error("Plugin Error:", e); }
    }
};

// --- DATA LOADING STRATEGY ---
async function loadData() {
    // 1. Try Disk
    try {
        const res = await fetch('data.json');
        if (res.ok) {
            const diskJson = await res.json();
            if (diskJson.config) {
                appData = diskJson.data || {};
                appConfig = migrateConfig(diskJson.config);
                console.log("Loaded from Disk");
                return;
            }
        }
    } catch(e) { /* ignore */ }

    // 2. Fallback to LocalStorage
    console.log("Loaded from LocalStorage");
    const localData = localStorage.getItem('fg_data');
    const localConfig = localStorage.getItem('fg_config');
    appData = localData ? JSON.parse(localData) : {};
    appConfig = localConfig ? migrateConfig(JSON.parse(localConfig)) : migrateConfig(DEFAULT_CONFIG);
}

// --- CORE FUNCTIONS ---
async function init() {
    // Force attributes on modal inputs
    const ids = ['inpTarget', 'inpStartDate', 'inpEndDate', 'inpSpecificDate'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if(el) {
            el.setAttribute('lang', 'en-GB');
            el.style.colorScheme = 'dark';
        }
    });

    await loadData();
    renderTable();
    setTimeout(renderCharts, 100);
}

function getMonday(d) {
    d = new Date(d);
    const day = d.getDay(), diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const m = new Date(d.setDate(diff)); m.setHours(0,0,0,0); return m;
}

function formatDateKey(d) {
    const offset = d.getTimezoneOffset();
    const local = new Date(d.getTime() - (offset*60*1000));
    return local.toISOString().split('T')[0];
}

function changeWeek(days) {
    currentMonday.setDate(currentMonday.getDate() + days);
    renderTable();
    renderCharts();
}

async function saveAll() {
    // Save to LocalStorage
    localStorage.setItem('fg_data', JSON.stringify(appData));
    localStorage.setItem('fg_config', JSON.stringify(appConfig));

    // Save to Disk (via Python)
    try {
        await fetch('/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ data: appData, config: appConfig })
        });
    } catch(e) {}
}

window.updateValue = function(dateKey, taskIdx, val) {
    if(!appData[dateKey]) appData[dateKey] = {};
    appData[dateKey][appConfig[taskIdx].name] = val;
    saveAll();
    renderRowScore(dateKey);
    renderCharts();
};

function parseTime(val) {
    if (!val) return null;
    try {
        const parts = val.split(':');
        return parseFloat(parts[0]) + parseFloat(parts[1])/60;
    } catch(e) { return null; }
}

function calculateStats(dateKey) {
    if(!appData[dateKey]) return { pct: 0, wake: null, sleep: null };

    let earned = 0, total = 0, wake = null, sleep = null;
    const [y, m, d] = dateKey.split('-').map(Number);
    const dt = new Date(y, m - 1, d);
    const dayShort = dt.toLocaleDateString('en-US', {weekday: 'short'});

    appConfig.forEach(task => {
        // 1. DATE RANGE CHECK
        if (dateKey < task.startDate || dateKey > task.endDate) return;

        // 2. DAY OF WEEK CHECK
        if(!task.days.includes(dayShort)) return;

        total += parseInt(task.weight);
        const val = appData[dateKey][task.name];

        if(task.type === 'time' && val) {
            const h = parseTime(val);
            if(task.name.toLowerCase().includes('wake')) wake = h;
            if(task.name.toLowerCase().includes('sleep')) {
                sleep = h < 12 ? h + 24 : h;
            }
        }

        if(task.type === 'bool' && val) earned += parseInt(task.weight);
        else if(task.type === 'score' && val !== undefined && val !== "") {
            const numVal = Math.min(100, Math.max(0, parseFloat(val)));
            earned += (numVal / 100) * task.weight;
        }
        else if(task.type === 'time' && val) {
            const h = parseTime(val);
            const targetH = parseTime(task.target);
            if (h !== null && targetH !== null) {
                const uMins = h * 60;
                const tMins = targetH * 60;
                const diff = uMins - tMins;
                if(task.condition === 'before') {
                    if(diff <= 0) earned += parseInt(task.weight);
                    else {
                        const penalty = (diff/30) * 0.2;
                        earned += Math.max(0, task.weight * (1 - penalty));
                    }
                } else {
                    if(diff >= 0) earned += parseInt(task.weight);
                }
            }
        }
    });

    return { pct: total === 0 ? 0 : (earned/total)*100, wake, sleep };
}

function renderTable() {
    const thead = document.getElementById('tableHeader');
    if (!thead) return;

    const end = new Date(currentMonday); end.setDate(end.getDate()+6);
    document.getElementById('lblWeek').innerText =
    `${currentMonday.toLocaleDateString(undefined, {month:'short', day:'numeric'})} - ${end.toLocaleDateString(undefined, {month:'short', day:'numeric'})}, ${end.getFullYear()}`;

    let weekDates = [];
    for(let i=0; i<7; i++) {
        const curr = new Date(currentMonday); curr.setDate(curr.getDate() + i);
        weekDates.push({ dateKey: formatDateKey(curr), dayShort: curr.toLocaleDateString('en-US', {weekday:'short'}), obj: curr });
    }

    // Build Headers
    thead.innerHTML = `<th>Day</th><th>Date</th>` +
    appConfig.map(t => `<th>${t.name}<br><span style="font-size:0.6em; opacity:0.7">${t.weight}pts</span></th>`).join('') +
    `<th>Score</th>`;

    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    weekDates.forEach(wd => {
        const tr = document.createElement('tr');
        tr.id = `row-${wd.dateKey}`;
        let html = `<td style="font-weight:bold; color:var(--ocean-cyan)">${wd.dayShort}</td><td>${wd.obj.getDate()}/${wd.obj.getMonth()+1}</td>`;

        appConfig.forEach((task, idx) => {
            const isActiveDate = wd.dateKey >= task.startDate && wd.dateKey <= task.endDate;
            const isActiveDay = task.days.includes(wd.dayShort);

            if(!isActiveDate || !isActiveDay) {
                html += `<td class="na-cell">--</td>`;
            } else {
                const val = appData[wd.dateKey]?.[task.name];
                if(task.type === 'bool') {
                    html += `<td><input type="checkbox" ${val ? 'checked' : ''} onchange="updateValue('${wd.dateKey}', ${idx}, this.checked)"></td>`;
                } else if (task.type === 'score') {
                    html += `<td><input type="number" min="0" max="100" placeholder="0-100" value="${val || ''}" onchange="updateValue('${wd.dateKey}', ${idx}, this.value)" style="width:60px"></td>`;
                } else {
                    html += `<td><input type="time" value="${val || ''}" lang="en-GB" style="color-scheme: dark;" onchange="updateValue('${wd.dateKey}', ${idx}, this.value)"></td>`;
                }
            }
        });

        html += `<td class="score-cell" id="score-${wd.dateKey}">-</td>`;
        tr.innerHTML = html;
        tbody.appendChild(tr);
        renderRowScore(wd.dateKey);
    });
}

function renderRowScore(key) {
    const cell = document.getElementById(`score-${key}`);
    if(!cell) return;
    const stats = calculateStats(key);
    const p = Math.round(stats.pct);
    cell.innerText = `${p}%`;
    cell.className = 'score-cell ' + (p >= 80 ? 'score-high' : p >= 50 ? 'score-mid' : 'score-low');
}

function renderCharts() {
    if (typeof Chart === 'undefined') return;
    const canvasScore = document.getElementById('scoreChart');
    const canvasTime = document.getElementById('timeChart');
    if (!canvasScore || !canvasTime) return;

    const ctxScore = canvasScore.getContext('2d');
    const ctxTime = canvasTime.getContext('2d');

    const labels = [];
    const scores = [];
    const wakes = [];
    const sleeps = [];

    for (let i = -1; i <= 7; i++) {
        const d = new Date(currentMonday);
        d.setDate(d.getDate() + i);
        const key = formatDateKey(d);
        const displayLabel = d.getDate() + '/' + (d.getMonth() + 1);
        const stats = calculateStats(key);

        labels.push(displayLabel);
        scores.push(stats.pct);
        wakes.push(stats.wake);
        sleeps.push(stats.sleep);
    }

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
            x: {
                grid: { color: '#1e293b' },
                ticks: { color: '#94a3b8' },
                min: labels[1], max: labels[7]
            },
            y: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } }
        }
    };

    if(chartRefs.score) chartRefs.score.destroy();
    chartRefs.score = new Chart(ctxScore, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'Efficiency (%)', data: scores, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', fill: true, tension: 0.3 }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { min: 0, max: 100 } } }
    });

    if(chartRefs.time) chartRefs.time.destroy();
    chartRefs.time = new Chart(ctxTime, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Wake Up', data: wakes, borderColor: '#06b6d4', backgroundColor: '#06b6d4', tension: 0.2, pointRadius: 4 },
                { label: 'Bedtime', data: sleeps, borderColor: '#8b5cf6', backgroundColor: '#8b5cf6', tension: 0.2, pointRadius: 4 }
            ]
        },
        plugins: [sleepConnectorPlugin],
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            let val = context.parsed.y;
                            if (val >= 24) val -= 24;
                            const h = Math.floor(val);
                            const m = Math.round((val - h) * 60);
                            return `${label}: ${h.toString().padStart(2, '0')}:${m.toString().padStart(2,'0')}`;
                        }
                    }
                }
            },
            scales: {
                ...commonOptions.scales,
                y: {
                    min: 0, max: 30,
                    ticks: { callback: v => ((v>=24 ? v-24 : v)).toString().padStart(2,'0') + ":00", color: '#94a3b8' }
                }
            }
        }
    });
}

// --- FORM UI LOGIC ---

function toggleFormInputs() {
    const type = inpType.value;
    document.getElementById('timeFields').style.display = type === 'time' ? 'block' : 'none';
}

function toggleFreqInputs() {
    const isRepeat = document.getElementById('radioRepeat').checked;
    document.getElementById('divRepeatDates').style.display = isRepeat ? 'grid' : 'none';
    document.getElementById('divDaysSelector').style.display = isRepeat ? 'block' : 'none';
    document.getElementById('divOnceDate').style.display = isRepeat ? 'none' : 'block';
}

function showAddForm() {
    document.getElementById('formTitle').innerText = "Add New Task";
    document.getElementById('editIndex').value = "-1";
    document.getElementById('inpName').value = "";
    document.getElementById('inpWeight').value = "10";
    inpType.value = "bool";
    document.getElementById('inpTarget').value = "";

    // Default Freq
    document.getElementById('radioRepeat').checked = true;
    document.getElementById('inpStartDate').value = DEFAULT_START;
    document.getElementById('inpEndDate').value = DEFAULT_END;
    document.getElementById('inpSpecificDate').value = "";
    selectAllDays();

    toggleFormInputs();
    toggleFreqInputs();
    form.style.display = 'block';
    document.getElementById('mainModalActions').style.display = 'none';
}

function hideForm() {
    form.style.display = 'none';
    document.getElementById('mainModalActions').style.display = 'flex';
}

function selectAllDays() {
    document.querySelectorAll('.day-chk').forEach(c => c.checked = true);
}

// --- TASK MANAGEMENT ---
function renderTaskList() {
    const container = document.getElementById('taskListContainer');
    container.innerHTML = '';
    appConfig.forEach((task, idx) => {
        const div = document.createElement('div');
        div.className = 'task-list-item';

        let freqLabel = "";
        if (task.startDate === task.endDate) {
            freqLabel = `On ${task.startDate}`;
        } else {
            freqLabel = `Repeating (${task.startDate} to ${task.endDate})`;
        }

        div.innerHTML = `
        <div>
        <strong style="color:var(--ocean-cyan)">${task.name}</strong>
        <span style="font-size:0.8em; color:var(--text-muted)">(${task.type}, ${task.weight}pts)</span>
        <div style="font-size:0.75em; margin-top:2px;">${freqLabel}</div>
        <div style="font-size:0.7em; color:#666;">${task.days.replace(/,/g, ' ')}</div>
        </div>
        <div class="task-actions">
        <button class="icon-btn secondary" onclick="moveTask(${idx}, -1)" ${idx === 0 ? 'disabled style="opacity:0.3"' : ''}>↑</button>
        <button class="icon-btn secondary" onclick="moveTask(${idx}, 1)" ${idx === appConfig.length - 1 ? 'disabled style="opacity:0.3"' : ''}>↓</button>
        <button class="secondary" style="padding:4px 8px; font-size:0.8rem" onclick="editTask(${idx})">Edit</button>
        <button style="padding:4px 8px; font-size:0.8rem; border-color:#f43f5e; color:#f43f5e; background:transparent" onclick="deleteTask(${idx})">X</button>
        </div>
        `;
        container.appendChild(div);
    });
}

window.editTask = function(idx) {
    const task = appConfig[idx];
    document.getElementById('formTitle').innerText = "Edit Task";
    document.getElementById('editIndex').value = idx;
    document.getElementById('inpName').value = task.name;
    document.getElementById('inpWeight').value = task.weight;
    inpType.value = task.type;
    document.getElementById('inpTarget').value = task.target || "";
    document.getElementById('inpCondition').value = task.condition || "before";

    if (task.startDate === task.endDate && task.startDate !== "") {
        document.getElementById('radioOnce').checked = true;
        document.getElementById('inpSpecificDate').value = task.startDate;
    } else {
        document.getElementById('radioRepeat').checked = true;
        document.getElementById('inpStartDate').value = task.startDate;
        document.getElementById('inpEndDate').value = task.endDate;
    }

    document.querySelectorAll('.day-chk').forEach(c => c.checked = task.days.includes(c.value));

    toggleFormInputs();
    toggleFreqInputs();
    form.style.display = 'block';
    document.getElementById('mainModalActions').style.display = 'none';
};

function saveTaskFromForm() {
    const idx = parseInt(document.getElementById('editIndex').value);
    const name = document.getElementById('inpName').value;
    if(!name) { alert("Name required"); return; }

    const isOnce = document.getElementById('radioOnce').checked;
    let startDate, endDate, days;

    if (isOnce) {
        const specDate = document.getElementById('inpSpecificDate').value;
        if(!specDate) { alert("Please select a date."); return; }
        startDate = specDate;
        endDate = specDate;
        const [y, m, d] = specDate.split('-').map(Number);
        const dt = new Date(y, m - 1, d);
        days = dt.toLocaleDateString('en-US', {weekday: 'short'});
    } else {
        startDate = document.getElementById('inpStartDate').value;
        endDate = document.getElementById('inpEndDate').value;
        if(!startDate || !endDate) { alert("Start and End dates required."); return; }

        days = Array.from(document.querySelectorAll('.day-chk:checked')).map(c=>c.value).join(',');
        if(!days) { alert("Select at least one day of the week."); return; }
    }

    const newTask = {
        name: name,
        weight: parseInt(document.getElementById('inpWeight').value),
        type: inpType.value,
        days: days,
        target: document.getElementById('inpTarget').value,
        condition: document.getElementById('inpCondition').value,
        startDate: startDate,
        endDate: endDate
    };

    if(idx === -1) appConfig.push(newTask);
    else appConfig[idx] = newTask;

    saveAll();
    renderTaskList();
    hideForm();
}

// --- HELPERS ---
function openModal() { renderTaskList(); hideForm(); modal.style.display = 'flex'; }
function closeModal() { modal.style.display = 'none'; renderTable(); renderCharts(); }

window.deleteTask = function(idx) {
    if(confirm("Delete this task?")) {
        appConfig.splice(idx, 1);
        saveAll();
        renderTaskList();
    }
};

window.moveTask = function(idx, direction) {
    if (direction === -1 && idx > 0) {
        [appConfig[idx], appConfig[idx - 1]] = [appConfig[idx - 1], appConfig[idx]];
    } else if (direction === 1 && idx < appConfig.length - 1) {
        [appConfig[idx], appConfig[idx + 1]] = [appConfig[idx + 1], appConfig[idx]];
    }
    saveAll();
    renderTaskList();
};

"""
Prosta aplikacja webowa do ekstrakcji danych z eCRF Diagram.
Uruchom: python3 app.py
Otwórz:  http://localhost:5000
"""

import json
import threading
import webbrowser
from flask import Flask, render_template_string, request, jsonify

from ecrf_extractor import ECRFExtractor, build_clean_json

app = Flask(__name__)

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>eCRF Diagram – Ekstraktor</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f0f2f5;
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 40px 16px;
    }

    .container { width: 100%; max-width: 900px; }

    h1 {
      font-size: 1.4rem;
      font-weight: 600;
      color: #1a1a2e;
      margin-bottom: 24px;
    }

    .card {
      background: #fff;
      border-radius: 12px;
      padding: 28px;
      box-shadow: 0 2px 12px rgba(0,0,0,.08);
      margin-bottom: 24px;
    }

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 16px;
      margin-bottom: 20px;
    }

    @media (max-width: 600px) { .form-row { grid-template-columns: 1fr; } }

    label { display: block; font-size: .8rem; color: #666; margin-bottom: 6px; }

    input[type=text], input[type=password] {
      width: 100%;
      padding: 10px 14px;
      border: 1.5px solid #ddd;
      border-radius: 8px;
      font-size: .95rem;
      outline: none;
      transition: border-color .2s;
    }
    input:focus { border-color: #4f8ef7; }

    button[type=submit] {
      background: #4f8ef7;
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 11px 32px;
      font-size: .95rem;
      font-weight: 600;
      cursor: pointer;
      transition: background .2s;
    }
    button:hover  { background: #3a7de6; }
    button:disabled { background: #a0b8f0; cursor: not-allowed; }

    /* Status */
    #status {
      display: none;
      align-items: center;
      gap: 10px;
      font-size: .9rem;
      color: #555;
      margin-top: 16px;
    }
    .spinner {
      width: 18px; height: 18px;
      border: 2.5px solid #ddd;
      border-top-color: #4f8ef7;
      border-radius: 50%;
      animation: spin .7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Error */
    .error {
      background: #fff0f0;
      border: 1.5px solid #f5c6cb;
      border-radius: 8px;
      padding: 14px 18px;
      color: #c0392b;
      font-size: .9rem;
    }

    /* Result */
    #result { display: none; }

    .result-header {
      margin-bottom: 24px;
    }
    .result-header h2 { font-size: 1.1rem; color: #1a1a2e; }

    /* Patient summary */
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }
    .summary-item {
      background: #f8f9fb;
      border-radius: 8px;
      padding: 12px 14px;
    }
    .summary-item .key   { font-size: .75rem; color: #888; margin-bottom: 3px; }
    .summary-item .value { font-size: .95rem; font-weight: 600; color: #1a1a2e; }

    /* Arm badge */
    .badge {
      display: inline-block;
      border-radius: 20px;
      padding: 3px 12px;
      font-size: .8rem;
      font-weight: 600;
    }
    .badge-exp  { background: #e8f4fd; color: #1a6fb3; }
    .badge-comp { background: #e8f8f0; color: #1a7f47; }

    /* Vessels */
    .vessel-card {
      border: 1.5px solid #e8eaf0;
      border-radius: 10px;
      margin-bottom: 16px;
      overflow: hidden;
    }
    .vessel-header {
      background: #f8f9fb;
      padding: 12px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1.5px solid #e8eaf0;
    }
    .vessel-title { font-weight: 700; font-size: 1rem; color: #1a1a2e; }
    .culprit-badge {
      background: #fdecea;
      color: #c0392b;
      border-radius: 20px;
      padding: 2px 10px;
      font-size: .75rem;
      font-weight: 700;
    }

    .vessel-body {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 0;
    }
    .vfield {
      padding: 10px 18px;
      border-bottom: 1px solid #f0f2f5;
      border-right: 1px solid #f0f2f5;
    }
    .vfield .vkey   { font-size: .73rem; color: #999; margin-bottom: 2px; }
    .vfield .vval   { font-size: .92rem; font-weight: 600; color: #222; }
    .vval-pos { color: #1a7f47; }
    .vval-neg { color: #c0392b; }
    .vval-na  { color: #aaa; font-weight: 400; }

    /* Stents */
    .stents-section { padding: 12px 18px; background: #fafbfc; }
    .stents-title   { font-size: .78rem; color: #888; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
    .stent-row      { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 4px; }
    .stent-chip {
      background: #e8f4fd;
      color: #1a6fb3;
      border-radius: 6px;
      padding: 4px 12px;
      font-size: .85rem;
      font-weight: 600;
    }

  </style>
</head>
<body>
<div class="container">
  <h1>eCRF Diagram — Ekstraktor danych angiograficznych</h1>

  <div class="card">
    <form id="form">
      <div class="form-row">
        <div>
          <label>Numer pacjenta</label>
          <input type="text" id="patient" name="patient"
                 placeholder="np. 1701-0031" pattern="\\d{4}-\\d{4}" required>
        </div>
        <div>
          <label>Login</label>
          <input type="text" id="login" name="login" placeholder="login" required>
        </div>
        <div>
          <label>Hasło</label>
          <input type="password" id="password" name="password" placeholder="hasło" required>
        </div>
      </div>
      <div style="font-size:.8rem; color:#999; margin-top:8px;">
        Login i hasło są zapisane lokalnie w przeglądarce
      </div>
      <button type="submit" id="btn">Wyciągnij dane</button>
    </form>

    <div id="status">
      <div class="spinner"></div>
      <span id="status-text">Łączenie z eCRF...</span>
    </div>

    <div id="progress-container" style="display:none; width:100%; margin-top:16px;">
      <div style="background:#f0f2f5; border-radius:3px; height:8px; overflow:hidden;">
        <div id="progress-bar" style="width:0%; background:#4f8ef7; height:100%; transition:width 0.3s ease-out;"></div>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:8px;">
        <div style="text-align:center;">
          <div id="progress-text" style="font-size:1.2rem; font-weight:700; color:#4f8ef7;">0%</div>
          <div style="font-size:0.75rem; color:#999;">Postęp</div>
        </div>
        <div style="text-align:center;">
          <div id="timer-text" style="font-size:1.2rem; font-weight:700; color:#666;">0s</div>
          <div style="font-size:0.75rem; color:#999;">Czas ekstrakcji</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Sekcja ładowania pliku -->
  <div class="card" id="file-card">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
      <span style="font-size:.85rem; font-weight:600; color:#555;">Załaduj wyniki z pliku JSON</span>
      <span id="loaded-count" style="font-size:.78rem; color:#aaa;"></span>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <label for="file-input" style="
        display:inline-block; cursor:pointer;
        background:#f0f2f5; border:1.5px solid #ddd;
        border-radius:8px; padding:9px 20px;
        font-size:.88rem; font-weight:600; color:#444;
        transition:background .2s;
      " onmouseover="this.style.background='#e4e7ec'" onmouseout="this.style.background='#f0f2f5'">
        Wybierz pliki
      </label>
      <input type="file" id="file-input" accept=".json" multiple style="display:none;">
      <button type="button" id="clear-btn" onclick="clearAllLoaded()" style="
        background:none; border:1.5px solid #f5c6cb; border-radius:8px;
        padding:9px 16px; font-size:.85rem; color:#c0392b; cursor:pointer;
        display:none;
      ">Wyczyść wszystkie</button>
    </div>
    <div id="loaded-list" style="margin-top:12px; display:flex; flex-wrap:wrap; gap:8px;"></div>
  </div>

  <div id="result">
    <div id="patients-container"></div>
  </div>
</div>

<script>
let lastJson = null;
let progressInterval = null;
let loadedPatients = [];   // [{id, filename, data}]

// ── Wczytywanie plików JSON ──────────────────────────────────────────────────
document.getElementById('file-input').addEventListener('change', function(e) {
  const files = Array.from(e.target.files);
  if (!files.length) return;

  let pending = files.length;
  files.forEach(file => {
    const reader = new FileReader();
    reader.onload = function(ev) {
      try {
        const data = JSON.parse(ev.target.result);
        const id = Date.now() + Math.random();
        // Sprawdź czy już załadowany (po numerze pacjenta)
        const num = data.patient && data.patient.randomization_number;
        if (num && loadedPatients.some(p => p.data.patient && p.data.patient.randomization_number === num)) {
          console.warn('Pacjent ' + num + ' już załadowany — pomijam');
        } else {
          loadedPatients.push({ id, filename: file.name, data });
        }
      } catch(err) {
        alert('Błąd parsowania ' + file.name + ': ' + err.message);
      }
      pending--;
      if (pending === 0) {
        renderAllLoaded();
      }
    };
    reader.readAsText(file);
  });

  // Reset input żeby można było wybrać ten sam plik ponownie
  e.target.value = '';
});

function removeLoaded(id) {
  loadedPatients = loadedPatients.filter(p => p.id !== id);
  renderAllLoaded();
}

function clearAllLoaded() {
  loadedPatients = [];
  renderAllLoaded();
}

function renderAllLoaded() {
  const list = document.getElementById('loaded-list');
  const countEl = document.getElementById('loaded-count');
  const clearBtn = document.getElementById('clear-btn');
  const result = document.getElementById('result');
  const container = document.getElementById('patients-container');

  // Chipsy z załadowanymi plikami
  list.innerHTML = loadedPatients.map(p => {
    const num = (p.data.patient && p.data.patient.randomization_number) || p.filename;
    return `<span style="
      display:inline-flex; align-items:center; gap:6px;
      background:#e8f4fd; color:#1a6fb3;
      border-radius:20px; padding:4px 12px 4px 10px;
      font-size:.8rem; font-weight:600;
    ">
      ${num}
      <span onclick="removeLoaded(${p.id})" style="cursor:pointer; color:#999; font-size:1rem; line-height:1;" title="Usuń">×</span>
    </span>`;
  }).join('');

  const n = loadedPatients.length;
  countEl.textContent = n ? `${n} załadowanych` : '';
  clearBtn.style.display = n ? 'inline-block' : 'none';

  if (!n) {
    result.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  result.style.display = 'block';
  container.innerHTML = loadedPatients.map(p => buildPatientCard(p.data, null, p.id)).join('');
}

// ── Dźwięk dzwonka ──────────────────────────────────────────────────────────
function playBellSound() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) {
      console.warn('AudioContext not supported');
      return;
    }

    const ctx = new AudioContext();
    const now = ctx.currentTime;

    // Master volume
    const masterGain = ctx.createGain();
    masterGain.gain.setValueAtTime(0.5, now);
    masterGain.connect(ctx.destination);

    // Główny ton dzwonka (800→600Hz sweep)
    const mainOsc = ctx.createOscillator();
    mainOsc.type = 'sine';
    mainOsc.frequency.setValueAtTime(800, now);
    mainOsc.frequency.exponentialRampToValueAtTime(600, now + 0.4);

    const mainGain = ctx.createGain();
    mainGain.gain.setValueAtTime(0.6, now);
    mainGain.gain.exponentialRampToValueAtTime(0.05, now + 0.4);

    mainOsc.connect(mainGain);
    mainGain.connect(masterGain);
    mainOsc.start(now);
    mainOsc.stop(now + 0.4);

    // Harmonika (wyższy ton)
    const harmOsc = ctx.createOscillator();
    harmOsc.type = 'sine';
    harmOsc.frequency.setValueAtTime(1200, now);
    harmOsc.frequency.exponentialRampToValueAtTime(900, now + 0.4);

    const harmGain = ctx.createGain();
    harmGain.gain.setValueAtTime(0.3, now);
    harmGain.gain.exponentialRampToValueAtTime(0.02, now + 0.4);

    harmOsc.connect(harmGain);
    harmGain.connect(masterGain);
    harmOsc.start(now);
    harmOsc.stop(now + 0.4);

    // Drugi ping (ding-dong efekt)
    setTimeout(() => {
      try {
        const ctx2 = new AudioContext();
        const now2 = ctx2.currentTime;

        const masterGain2 = ctx2.createGain();
        masterGain2.gain.setValueAtTime(0.5, now2);
        masterGain2.connect(ctx2.destination);

        const osc2 = ctx2.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(600, now2);
        osc2.frequency.exponentialRampToValueAtTime(400, now2 + 0.3);

        const gain2 = ctx2.createGain();
        gain2.gain.setValueAtTime(0.5, now2);
        gain2.gain.exponentialRampToValueAtTime(0.05, now2 + 0.3);

        osc2.connect(gain2);
        gain2.connect(masterGain2);
        osc2.start(now2);
        osc2.stop(now2 + 0.3);
      } catch(e) {
        console.warn('Second bell tone failed:', e);
      }
    }, 200);

    console.log('✓ Bell sound playing');

  } catch(e) {
    console.warn('Bell sound error:', e);
  }
}

// ── Zapamiętywanie loginu i hasła ────────────────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
  const savedLogin = localStorage.getItem('ecrf_login');
  const savedPassword = localStorage.getItem('ecrf_password');
  if (savedLogin) document.getElementById('login').value = savedLogin;
  if (savedPassword) document.getElementById('password').value = savedPassword;
});

function val(v, pos='vval-pos', neg='vval-neg') {
  if (v === null || v === undefined) return '<span class="vval vval-na">—</span>';
  if (v === true)  return `<span class="vval ${pos}">TAK</span>`;
  if (v === false) return `<span class="vval ${neg}">NIE</span>`;
  return `<span class="vval">${v}</span>`;
}

function buildPatientCard(data, totalSeconds, pid) {
  if (!data || !data.patient) {
    return '<div class="error">Błąd: puste dane</div>';
  }
  const p = data.patient;

  let html = `<div class="card" style="position:relative;">`;

  // Przycisk usuń (tylko dla załadowanych z pliku)
  if (pid !== undefined) {
    html += `<button onclick="removeLoaded(${pid})" title="Usuń tego pacjenta" style="
      position:absolute; top:14px; right:14px;
      background:none; border:none; cursor:pointer;
      color:#ccc; font-size:1.2rem; line-height:1;
    ">×</button>`;
  }

  html += `<h3 style="font-size:1rem; font-weight:700; color:#1a1a2e; margin-bottom:14px;">
    Pacjent ${p.randomization_number}
    ${p.arm ? `<span style="font-size:.78rem; font-weight:400; color:#888; margin-left:8px;">${p.arm}</span>` : ''}
  </h3>`;

  html += '<pre style="background:#f8f9fb; padding:14px 16px; border-radius:8px; overflow-x:auto; font-size:.88rem; margin-bottom:16px;">';
  html += `<strong>Ramię:</strong> ${p.arm || '—'}   <strong>Płeć:</strong> ${p.sex || '—'}   <strong>LVEF:</strong> ${p.lvef || '—'}   <strong>NYHA:</strong> ${p.nyha || '—'}\n`;
  html += `<strong>Cukrzyca:</strong> ${p.diabetes === true ? 'Tak' : p.diabetes === false ? 'Nie' : '—'}   `;
  html += `<strong>Nadciśnienie:</strong> ${p.hypertension === true ? 'Tak' : p.hypertension === false ? 'Nie' : '—'}   `;
  html += `<strong>Poprzednie PCI:</strong> ${p.previous_pci === true ? 'Tak' : p.previous_pci === false ? 'Nie' : '—'}\n`;
  if (totalSeconds) html += `\n<strong style="color:#4f8ef7;">⏱ Czas ekstrakcji:</strong> ${totalSeconds}s\n`;
  html += '</pre>';

  if (data.vessels && data.vessels.length) {
    html += '<div style="font-size:.78rem; color:#888; font-weight:600; text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px;">Naczynia</div>';
    data.vessels.forEach((v, i) => {
      html += `<div style="border:1.5px solid #e8eaf0; border-radius:8px; margin-bottom:10px; padding:11px 14px; background:#fafbfc;">`;
      html += `<div style="font-weight:700; color:${v.culprit ? '#c0392b' : '#1a1a2e'}; margin-bottom:6px;">`;
      html += `Naczynie ${i+1}: ${v.segment}${v.culprit ? ' ★ CULPRIT' : ''}</div>`;
      html += `<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:4px 16px; font-size:.85rem;">`;
      html += `<span>Stenoza: <b>${v.stenosis_pct !== null ? v.stenosis_pct + '%' : '—'}</b></span>`;
      html += `<span>TIMI pre: <b>${v.timi_pre !== null ? ['0','I','II','III'][v.timi_pre] : '—'}</b></span>`;
      html += `<span>TIMI post: <b>${v.timi_post !== null ? ['0','I','II','III'][v.timi_post] : '—'}</b></span>`;
      html += `<span>FFR: <b>${v.ffr_adenosine !== null ? v.ffr_adenosine : '—'}</b></span>`;
      if (v.pd_pa !== null || v.rfr !== null) {
        html += `<span>Pd/Pa: <b>${v.pd_pa ?? '—'}</b></span>`;
        html += `<span>RFR: <b>${v.rfr ?? '—'}</b></span>`;
      }
      html += `<span>OCT pre: <b style="color:${v.oct_pre ? '#2ecc71' : '#999'}">${v.oct_pre ? 'TAK' : 'NIE'}</b></span>`;
      html += `<span>Bifurcation: <b style="color:${v.bifurcation === true ? '#c0392b' : v.bifurcation === false ? '#2ecc71' : '#999'}">${v.bifurcation === true ? 'TAK' : v.bifurcation === false ? 'NIE' : '—'}</b></span>`;
      html += `<span>Predilatation: <b style="color:${v.predilatation === true ? '#2ecc71' : '#999'}">${v.predilatation === true ? 'TAK' : v.predilatation === false ? 'NIE' : '—'}</b></span>`;
      html += `<span>Stent: <b style="color:${v.stent_placed === true ? '#2ecc71' : '#999'}">${v.stent_placed === true ? 'TAK' : v.stent_placed === false ? 'NIE' : '—'}</b></span>`;
      html += `<span>PCI: <b style="color:${v.pci_performed ? '#2ecc71' : '#999'}">${v.pci_performed ? 'TAK' : 'NIE'}</b></span>`;
      if (v.pci_successful !== null) {
        html += `<span>PCI sukces: <b style="color:${v.pci_successful ? '#2ecc71' : '#c0392b'}">${v.pci_successful ? 'TAK' : 'NIE'}</b></span>`;
      }
      html += `</div>`;
      if (v.stents && v.stents.length) {
        html += `<div style="font-size:.82rem; color:#1a6fb3; margin-top:6px;">Stenty: ${v.stents.map(s => `${s.type || 'stent'} ${s.diameter_mm}×${s.length_mm}mm`).join(' | ')}</div>`;
      }
      html += `</div>`;
    });
  }

  html += `</div>`;
  return html;
}

function renderResult(data, totalSeconds) {
  console.log('renderResult called with:', data, 'Time:', totalSeconds + 's');
  lastJson = data;

  if (!data || !data.patient) {
    document.getElementById('patients-container').innerHTML = '<div class="error">Błąd: puste dane</div>';
    document.getElementById('result').style.display = 'block';
    return;
  }

  // Dodaj do kolekcji załadowanych
  const num = data.patient.randomization_number;
  const alreadyIdx = loadedPatients.findIndex(p => p.data.patient && p.data.patient.randomization_number === num);
  const id = alreadyIdx >= 0 ? loadedPatients[alreadyIdx].id : Date.now() + Math.random();
  const entry = { id, filename: `result_${num}.json`, data };
  if (alreadyIdx >= 0) {
    loadedPatients[alreadyIdx] = entry;  // odśwież
  } else {
    loadedPatients.push(entry);
  }

  renderAllLoaded();
  playBellSound();
}

document.getElementById('form').addEventListener('submit', async e => {
  e.preventDefault();

  // Zapisz login i hasło
  localStorage.setItem('ecrf_login', document.getElementById('login').value);
  localStorage.setItem('ecrf_password', document.getElementById('password').value);

  const btn    = document.getElementById('btn');
  const status = document.getElementById('status');
  const stText = document.getElementById('status-text');
  const progressContainer = document.getElementById('progress-container');
  const progressBar = document.getElementById('progress-bar');
  const progressText = document.getElementById('progress-text');
  const timerText = document.getElementById('timer-text');

  btn.disabled = true;
  status.style.display = 'flex';
  progressContainer.style.display = 'block';
  document.getElementById('result').style.display = 'none';

  // Reset progress
  let progress = 0;
  progressBar.style.width = '0%';
  progressText.textContent = '0%';
  timerText.textContent = '0s';

  // Animuj progress bar i timer
  const startTime = Date.now();
  const maxDuration = 45000; // 45 sekund max

  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    const elapsed = Date.now() - startTime;
    const elapsedSeconds = Math.floor(elapsed / 1000);

    // Update timer
    timerText.textContent = elapsedSeconds + 's';

    // Quadratic easing: szybko na początku, wolnie na koniec
    progress = Math.min(95, (elapsed / maxDuration) * 100);
    progressBar.style.width = progress.toFixed(0) + '%';
    progressText.textContent = progress.toFixed(0) + '%';
  }, 200);

  const steps = [
    'Logowanie do eCRF...',
    'Szukam pacjenta w BrowseSubjects...',
    'Ładuję sekcje CRF...',
    'Wyciągam dane formularzy...',
  ];
  let i = 0;
  const tick = setInterval(() => { stText.textContent = steps[Math.min(++i, steps.length-1)]; }, 12000);

  try {
    const resp = await fetch('/extract', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        patient:  document.getElementById('patient').value.trim(),
        login:    document.getElementById('login').value.trim(),
        password: document.getElementById('password').value,
      })
    });

    const data = await resp.json();
    clearInterval(tick);
    clearInterval(progressInterval);

    // Calculate total extraction time
    const totalTime = (Date.now() - startTime) / 1000;
    const totalSeconds = totalTime.toFixed(2);

    // Finish progress bar and timer
    progressBar.style.width = '100%';
    progressText.textContent = '100%';
    timerText.textContent = totalSeconds + 's';

    // Visual notification (flash green)
    progressBar.style.background = '#2ecc71';
    setTimeout(() => { progressBar.style.background = '#4f8ef7'; }, 200);
    setTimeout(() => { progressBar.style.background = '#2ecc71'; }, 400);
    setTimeout(() => { progressBar.style.background = '#4f8ef7'; }, 600);

    if (!resp.ok || data.error) {
      document.getElementById('result').style.display = 'block';
      document.getElementById('patients-container').innerHTML =
        `<div class="card"><div class="error">❌ ${data.error || 'Nieznany błąd'}</div></div>`;
    } else {
      try {
        renderResult(data, totalSeconds);
      } catch(err) {
        document.getElementById('result').style.display = 'block';
        document.getElementById('patients-container').innerHTML =
          `<div class="card"><div class="error">Błąd renderowania: ${err.message}</div></div>`;
        console.error('Render error:', err);
      }
    }
  } catch(err) {
    clearInterval(tick);
    clearInterval(progressInterval);
    const totalTime = (Date.now() - startTime) / 1000;
    const totalSeconds = totalTime.toFixed(2);
    timerText.textContent = totalSeconds + 's';
    document.getElementById('result').style.display = 'block';
    document.getElementById('patients-container').innerHTML =
      `<div class="card"><div class="error">❌ Błąd połączenia: ${err.message}</div></div>`;
  }

  btn.disabled = false;
  status.style.display = 'none';
  progressContainer.style.display = 'none';
});
</script>
</body>
</html>
"""

# ── Backend ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/extract", methods=["POST"])
def extract():
    body = request.get_json(force=True)
    patient  = body.get("patient", "").strip()
    login    = body.get("login", "").strip()
    password = body.get("password", "")

    import re
    if not re.match(r"^\d{4}-\d{4}$", patient):
        return jsonify({"error": f"Nieprawidłowy format numeru: '{patient}'. Oczekiwany: XXXX-AAAA"}), 400

    try:
        with ECRFExtractor(headless=True) as ex:
            data = ex.extract(login, password, patient)
        clean = build_clean_json(data)

        # Zapisz też lokalnie
        with open(f"result_{patient}.json", "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)

        return jsonify(clean)

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Błąd ekstrakcji: {e}"}), 500


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PORT = 5555
    URL  = f"http://localhost:{PORT}"
    print(f"\n  eCRF Diagram Extractor — Web UI")
    print(f"  Otwieranie przeglądarki: {URL}\n")
    threading.Timer(1.2, lambda: webbrowser.open(URL)).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)

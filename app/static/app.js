const API = "";
let patientId = null;
let currentData = null;
let lastASAM = null;
let lastTJC = null;
let currentSourceDoc = null;
let currentLinkedEvidence = [];

/* ── Toast ── */
function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  requestAnimationFrame(() =>
    requestAnimationFrame(() => el.classList.add("show")),
  );
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

/* ── Evaluations Store (handled by history panel) ── */
function addEvaluation() {}

function loadEvaluation() {}

/* ── Activity Log ── */
function logActivity(type, message) {
  const log = document.getElementById("activity-log");
  if (log.querySelector("div[style]")) log.innerHTML = "";
  const now = new Date();
  const time = now.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const date = now.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
  const item = document.createElement("div");
  item.className = "log-item log-" + type;
  item.innerHTML = `${message}<div class="log-time">${date}, ${time}</div>`;
  log.prepend(item);
}

/* ── Navigation ── */
function showView(view) {
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.remove("active");
  });
  document
    .querySelectorAll(".sidebar-item")
    .forEach((i) => i.classList.remove("active"));
  // Small delay for fade effect
  setTimeout(() => {
    document.getElementById("view-" + view).classList.add("active");
  }, 30);
  const nav = document.getElementById("nav-" + view);
  if (nav) nav.classList.add("active");
}

function selectPatient(id) {
  patientId = id;
  showView("patient");
  document
    .querySelectorAll(".sidebar-patient")
    .forEach((p) => p.classList.toggle("active", p.dataset.id === id));
  document
    .querySelectorAll(".sidebar-item")
    .forEach((i) => i.classList.remove("active"));
  loadHistory(id);
}

/* ── History ── */
async function loadHistory(pid) {
  const panel = document.getElementById("history-panel");
  const items = document.getElementById("history-items");
  try {
    const [asamRes, tjcRes] = await Promise.all([
      fetch(`${API}/api/v1/patients/${pid}/asam-history`),
      fetch(`${API}/api/v1/patients/${pid}/tjc-history`),
    ]);
    const asamHistory = asamRes.ok ? await asamRes.json() : [];
    const tjcHistory = tjcRes.ok ? await tjcRes.json() : [];

    if (asamHistory.length === 0 && tjcHistory.length === 0) {
      panel.style.display = "none";
      return;
    }

    let html = "";
    for (const e of asamHistory) {
      const date = new Date(e.evaluated_at).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
      const acc =
        e.qa_accuracy != null ? `${(e.qa_accuracy * 100).toFixed(0)}%` : "--";
      const accColor =
        e.qa_accuracy >= 0.9
          ? "#6ee7b7"
          : e.qa_accuracy >= 0.7
            ? "#fde68a"
            : "#fca5a5";
      html += `<div class="history-item" onclick="loadHistoryItem('asam','${pid}','${e.id}')">
        <div class="history-item-type">ASAM — Level ${escHtml(e.recommended_level)}</div>
        <div class="history-item-detail">${date} · <span style="color:${accColor};font-weight:700">${acc}</span> verified</div>
      </div>`;
    }
    for (const a of tjcHistory) {
      const date = new Date(a.audited_at).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
      const acc =
        a.qa_accuracy != null ? `${(a.qa_accuracy * 100).toFixed(0)}%` : "--";
      const accColor =
        a.qa_accuracy >= 0.9
          ? "#6ee7b7"
          : a.qa_accuracy >= 0.7
            ? "#fde68a"
            : "#fca5a5";
      html += `<div class="history-item" onclick="loadHistoryItem('tjc','${pid}','${a.id}')">
        <div class="history-item-type">TJC — ${a.overall_compliance_pct?.toFixed(0) || "--"}% compliance</div>
        <div class="history-item-detail">${date} · <span style="color:${accColor};font-weight:700">${acc}</span> verified</div>
      </div>`;
    }

    items.innerHTML = html;
    panel.style.display = "block";
  } catch (e) {
    panel.style.display = "none";
  }
}

async function loadHistoryItem(type, pid, id) {
  try {
    const url =
      type === "asam"
        ? `${API}/api/v1/patients/${pid}/asam-history/${id}`
        : `${API}/api/v1/patients/${pid}/tjc-history/${id}`;
    const res = await fetch(url);
    if (!res.ok) return toast("Failed to load", "error");
    const d = await res.json();

    if (type === "asam") {
      lastASAM = d;
      currentSourceDoc = d.source_document || null;
      currentLinkedEvidence = d.linked_evidence || [];
      displayASAM(d);
      document.getElementById("tab-btn-asam").classList.remove("hidden");
      showTab("asam");
      if (d.qa_agent) renderQATerminal("asam", d.qa_agent);
      if (d.linked_evidence) buildDocReport("asam", { evaluation: d });
      toast(`Loaded ASAM — Level ${d.recommended_level}`, "info");
    } else {
      lastTJC = d;
      currentSourceDoc = d.source_document || null;
      currentLinkedEvidence = d.linked_evidence || [];
      displayTJC(d);
      document.getElementById("tab-btn-tjc").classList.remove("hidden");
      showTab("tjc");
      if (d.qa_agent) renderQATerminal("tjc", d.qa_agent);
      if (d.linked_evidence) buildDocReport("tjc", { audit: d });
      toast(
        `Loaded TJC — ${d.overall_compliance_percentage?.toFixed(1)}%`,
        "info",
      );
    }
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

/* ── Collapsible Dimensions ── */
function toggleDimension(el) {
  const body = el.nextElementSibling;
  const toggle = el.querySelector(".dimension-toggle");
  body.classList.toggle("collapsed");
  toggle.classList.toggle("open");
}

/* ── JSON Export ── */
function downloadJSON() {
  const payload = {};
  if (currentData) payload.extraction = currentData;
  if (lastASAM) payload.asam_evaluation = lastASAM;
  if (lastTJC) payload.tjc_audit = lastTJC;
  if (!Object.keys(payload).length)
    return toast("No data to export", "warning");
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `perspectives_${patientId || "export"}.json`;
  a.click();
  URL.revokeObjectURL(url);
  toast("JSON exported successfully", "success");
  logActivity("extract", "Exported JSON sample");
}

/* ── ASAM Report ── */
async function generateASAMReport() {
  if (!patientId) return toast("Extract patient data first", "warning");
  toast("Generating ASAM report...", "info");
  try {
    const r = await fetch(`${API}/api/v1/patients/${patientId}/asam-report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!r.ok) {
      const text = await r.text();
      try {
        const d = JSON.parse(text);
        throw new Error(d.detail || "Failed");
      } catch {
        throw new Error(text || "Report generation failed");
      }
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `asam_report_${patientId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast("ASAM report downloaded", "success");
    logActivity("asam", "Generated ASAM PDF report");
  } catch (e) {
    toast("Report error: " + e.message, "error");
  }
}

/* ── Extract ── */
async function parseExport() {
  const p = document.getElementById("export-path").value;
  const n = document.getElementById("client-name").value;
  if (!p || !n) return toast("Enter export path and client name", "warning");
  show("extract-loading");
  try {
    const r = await fetch(`${API}/api/v1/parse-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ export_path: p, client_name: n }),
    });
    const d = await r.json();
    if (d.detail) throw new Error(d.detail);
    onExtracted(d);
  } catch (e) {
    toast(e.message, "error");
  }
  hide("extract-loading");
}

async function extractLive() {
  const n = document.getElementById("client-name-live").value;
  const e = document.getElementById("sp-email").value;
  const p = document.getElementById("sp-password").value;
  show("live-loading");
  try {
    const r = await fetch(`${API}/api/v1/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_name: n || null,
        email: e || null,
        password: p || null,
      }),
    });
    const d = await r.json();
    if (d.detail) throw new Error(d.detail);
    // Handle multiple patients or single patient
    if (Array.isArray(d)) {
      for (const patient of d) onExtracted(patient);
      toast(`Extracted ${d.length} patients`, "success");
    } else {
      onExtracted(d);
    }
  } catch (e) {
    toast(e.message, "error");
  }
  hide("live-loading");
}

function onExtracted(d) {
  currentData = d;
  lastASAM = null;
  lastTJC = null;
  const p = d.patient;
  patientId = p.id;

  const list = document.getElementById("patient-list");
  if (list.querySelector("div[style]")) list.innerHTML = "";

  const existing = list.querySelector(`[data-id="${p.id}"]`);
  if (!existing) {
    const initials = (p.first_name[0] + p.last_name[0]).toUpperCase();
    let html = `<div class="sidebar-patient active" data-id="${p.id}" onclick="loadAndSelect('${p.id}')">
      <div class="sidebar-patient-avatar">${initials}</div>
      <div class="sidebar-patient-info">
        <div class="sidebar-patient-name">${p.first_name} ${p.last_name}</div>
        <div class="sidebar-patient-meta">${p.date_of_birth} | ${d.progress_notes.length} notes</div>
      </div>
    </div>
    <div class="sidebar-notes" data-patient="${p.id}">
      <div class="sidebar-note-item" onclick="loadAndSelect('${p.id}');showTab('assessment')">Assessment</div>`;
    for (const note of d.progress_notes)
      html += `<div class="sidebar-note-item" onclick="loadAndSelect('${p.id}');showTab('notes')">${note.note_format} - ${note.note_date}</div>`;
    html += `</div>`;
    list.insertAdjacentHTML("beforeend", html);
  }

  displayPatient(d);
  showView("patient");
  toast(
    `Extracted ${p.first_name} ${p.last_name} — ${d.progress_notes.length} notes`,
    "success",
  );
  logActivity(
    "extract",
    `Extracted ${p.first_name} ${p.last_name} — ${d.progress_notes.length} notes`,
  );
}

function displayPatient(d) {
  const p = d.patient;
  document.getElementById("patient-initials").textContent = (
    p.first_name[0] + p.last_name[0]
  ).toUpperCase();
  document.getElementById("patient-name").textContent =
    `${p.first_name} ${p.last_name}`;
  document.getElementById("patient-meta").textContent =
    `DOB: ${p.date_of_birth} | ${p.gender} | ${d.progress_notes.length} notes`;

  // Stats
  document.getElementById("stat-notes").textContent = d.progress_notes.length;
  document.getElementById("stat-dx").textContent = p.diagnoses?.length || 0;
  if (d.progress_notes.length > 0) {
    const lastDate = d.progress_notes[d.progress_notes.length - 1].note_date;
    document.getElementById("stat-last").textContent = lastDate;
  }

  const a = d.assessment;
  // Parse BPS into sections and render as collapsible cards
  function reflowText(t) {
    return t.replace(/\n{2,}/g, "\n\n").replace(/([^\n])\n([^\n])/g, "$1 $2");
  }
  const el = document.getElementById("assessment-content");
  function parseAssessmentSections(raw) {
    // Split out intake questionnaire if appended
    let mainText = raw;
    let intakeText = "";
    const intakeIdx = raw.indexOf("=== INTAKE QUESTIONNAIRE ===");
    if (intakeIdx !== -1) {
      mainText = raw.substring(0, intakeIdx).trim();
      intakeText = raw.substring(intakeIdx + 28).trim();
    }
    // Extract preamble (everything before first numbered section)
    const firstNum = mainText.match(/\n\d{1,2}\.\s+[A-Z]/);
    let preamble = "";
    if (firstNum) {
      preamble = mainText.substring(0, firstNum.index).trim();
      mainText = mainText.substring(firstNum.index);
    }
    // Split on numbered headers at line start
    const parts = mainText.split(/\n(?=\d{1,2}\.\s+[A-Z])/);
    const sections = [];
    const seenNums = new Set();
    for (const part of parts) {
      const m = part.match(/^(\d{1,2})\.\s+(.+?)(?:\n|$)([\s\S]*)/);
      if (m && !seenNums.has(m[1])) {
        seenNums.add(m[1]);
        sections.push({
          title: m[1] + ". " + m[2].replace(/:$/, "").trim(),
          body: reflowText(m[3].trim()),
        });
      }
    }
    if (intakeText) {
      sections.push({
        title: "Intake Questionnaire",
        body: reflowText(intakeText),
      });
    }
    return { preamble, sections };
  }

  function renderSections(preamble, sections) {
    let html = `<div style="margin-bottom:16px;padding:12px 16px;background:rgba(255,255,255,0.03);border-radius:10px;border:1px solid rgba(255,255,255,0.06);">
      <div style="font-size:13px;font-weight:600;color:rgba(255,255,255,0.6);">Clinician: ${a.clinician.name}</div>
      <div style="font-size:11px;color:rgba(255,255,255,0.3);margin-top:2px;">Date: ${a.assessment_date} | Type: ${a.assessment_type || "Biopsychosocial Intake"}</div>
    </div>`;
    if (preamble)
      html += `<div style="font-size:12px;color:rgba(255,255,255,0.35);margin-bottom:12px;">${preamble}</div>`;
    for (const s of sections) {
      html += `<div class="dimension" style="margin-bottom:10px;">
        <div class="dimension-header" onclick="toggleDimension(this)">
          <span class="dimension-name">${s.title}</span>
          <span class="dimension-toggle open">&#9662;</span>
        </div>
        <div class="dimension-body">
          <div style="font-size:13px;line-height:1.8;color:rgba(255,255,255,0.45);margin-top:8px;">${s.body.replace(/\n/g, "<br>")}</div>
        </div>
      </div>`;
    }
    el.innerHTML = html;
  }

  if (a.raw_text) {
    const { preamble, sections } = parseAssessmentSections(a.raw_text);
    renderSections(preamble, sections);
  } else {
    const sections = [
      { title: "Presenting Problem", body: a.presenting_problem || "" },
      {
        title: "History of Present Illness",
        body: a.history_of_present_illness || "",
      },
      {
        title: "Substance Use History",
        body: a.substance_use_history || "",
      },
      { title: "Medical History", body: a.medical_history || "" },
      { title: "Psychiatric History", body: a.psychiatric_history || "" },
      { title: "Family History", body: a.family_history || "" },
      { title: "Social History", body: a.social_history || "" },
      { title: "Spiritual/Cultural", body: a.spiritual_cultural || "" },
      { title: "Strengths", body: a.strengths || "" },
      { title: "Risk Assessment", body: a.risk_assessment || "" },
      { title: "Mental Status Exam", body: a.mental_status_exam || "" },
    ].filter((s) => s.body && s.body !== "Not documented");
    renderSections("", sections);
  }

  let h = "";
  for (const n of d.progress_notes) {
    h += `<div class="dimension"><div class="dimension-header" onclick="toggleDimension(this)"><span class="dimension-name">${n.note_format} — ${n.note_date}</span><span class="dimension-toggle open">&#9662;</span></div><div class="dimension-body"><div style="font-size:12px;margin-top:8px;color:rgba(255,255,255,0.4);">`;
    for (const [s, t] of Object.entries(n.sections))
      h += `<p style="margin-bottom:6px;"><strong style="color:rgba(255,255,255,0.6);">${s.toUpperCase()}:</strong> ${t.substring(0, 250)}${t.length > 250 ? "..." : ""}</p>`;
    h += "</div></div></div>";
  }
  document.getElementById("notes-content").innerHTML = h;

  document.getElementById("tab-btn-asam").classList.add("hidden");
  document.getElementById("tab-btn-tjc").classList.add("hidden");
  document.getElementById("tab-btn-report").classList.add("hidden");
  document.getElementById("tab-asam").classList.add("hidden");
  document.getElementById("tab-tjc").classList.add("hidden");
  document.getElementById("tab-report").classList.add("hidden");
  showTab("assessment");
}

/* ── ASAM ── */
async function runASAM() {
  if (!patientId) return toast("Extract patient data first", "warning");
  const r = await fetch(`${API}/api/v1/patients/${patientId}/extract`);
  if (!r.ok)
    return toast("Patient not found in database. Re-extract first.", "error");

  // Show terminal and switch to ASAM tab
  document.getElementById("tab-btn-asam").classList.remove("hidden");
  showTab("asam");
  document.getElementById("asam-qa").classList.remove("hidden");
  const terminal = document.getElementById("asam-qa-terminal");
  const badge = document.getElementById("asam-qa-badge");
  terminal.innerHTML = "";
  badge.textContent = "running...";
  badge.style.color = "#93c5fd";
  badge.style.background = "rgba(59,130,246,0.15)";

  // Reset display areas
  document.getElementById("asam-level").textContent = "--";
  document.getElementById("asam-level-name").textContent = "";
  document.getElementById("asam-rationale").textContent = "";
  document.getElementById("asam-summary").textContent = "";
  document.getElementById("asam-dimensions").innerHTML = "";
  document.getElementById("asam-steps").innerHTML = "";

  // Stream SSE
  try {
    const res = await fetch(
      `${API}/api/v1/patients/${patientId}/asam-evaluation/stream`,
      { method: "POST" },
    );
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      let eventType = null;
      for (const l of lines) {
        if (l.startsWith("event: ")) eventType = l.substring(7);
        else if (l.startsWith("data: ") && eventType) {
          try {
            const data = JSON.parse(l.substring(6));
            renderAgentEvent(terminal, eventType, data, "asam");
            terminal.scrollTop = terminal.scrollHeight;

            // Render the full ASAM report as soon as generation completes
            if (eventType === "initial_result" && data.evaluation) {
              displayASAM({ ...data.evaluation, qa_agent: null });
            }

            if (eventType === "complete") {
              lastASAM = {
                ...data.evaluation,
                source_document: data.source_document,
                linked_evidence: data.linked_evidence,
                qa_agent: {
                  accuracy: data.accuracy,
                  claims: data.claims,
                  trace: [],
                  unresolved_claims: [],
                },
              };
              currentSourceDoc = data.source_document;
              currentLinkedEvidence = data.linked_evidence || [];
              displayASAM({
                ...data.evaluation,
                qa_agent: null,
                linked_evidence: data.linked_evidence,
                source_document: data.source_document,
              });

              // Update badge
              const pct = (data.accuracy * 100).toFixed(1);
              const color =
                data.accuracy >= 0.9
                  ? "#6ee7b7"
                  : data.accuracy >= 0.7
                    ? "#fde68a"
                    : "#fca5a5";
              const bg =
                data.accuracy >= 0.9
                  ? "rgba(52,211,153,0.15)"
                  : data.accuracy >= 0.7
                    ? "rgba(251,191,36,0.15)"
                    : "rgba(248,113,113,0.15)";
              badge.textContent = `${pct}% verified`;
              badge.style.color = color;
              badge.style.background = bg;

              // Stats row
              const c = data.claims;
              terminal.innerHTML += `<div class="qa-stats-row">
                <div class="qa-stat"><div class="qa-stat-value" style="color:${color}">${pct}%</div><div class="qa-stat-label">Accuracy</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#6ee7b7">${c.verified}</div><div class="qa-stat-label">Verified</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#93c5fd">${c.fixed}</div><div class="qa-stat-label">Fixed</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#fde68a">${c.unsupported}</div><div class="qa-stat-label">Unsupported</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#fca5a5">${c.failed}</div><div class="qa-stat-label">Failed</div></div>
              </div>`;

              buildDocReport("asam", data);
              toast(
                `ASAM complete — Level ${data.evaluation.recommended_level}`,
                "success",
              );
              logActivity(
                "asam",
                `ASAM — Level ${data.evaluation.recommended_level} (${pct}% verified)`,
              );
              loadHistory(patientId);
            }
          } catch (e) {}
          eventType = null;
        }
      }
    }
  } catch (e) {
    toast("ASAM stream error: " + e.message, "error");
  }
}

function displayASAM(d) {
  document.getElementById("asam-level").textContent = d.recommended_level;
  document.getElementById("asam-level-name").textContent =
    d.recommended_level_name;
  document.getElementById("asam-rationale").textContent =
    d.level_rationale || "";
  document.getElementById("asam-summary").textContent =
    d.clinical_summary || "";
  let h = "";
  for (const dim of d.dimensions) {
    h += `<div class="dimension"><div class="dimension-header" onclick="toggleDimension(this)"><span class="dimension-name">D${dim.dimension_number}: ${dim.dimension_name}</span><span class="dimension-toggle open">&#9662;</span></div><div class="dimension-body">`;
    if (dim.subdimensions)
      for (const s of dim.subdimensions) {
        h += `<div style="margin:6px 0 2px 10px;font-size:12px;"><span class="risk-code">${s.risk_rating_code}</span> <strong style="color:rgba(255,255,255,0.7);">${s.name}</strong> <span style="color:rgba(255,255,255,0.25);">&rarr; ${s.minimum_level}</span><div style="color:rgba(255,255,255,0.3);margin-top:3px;">${s.rationale.substring(0, 220)}</div>`;
        if (s.citations?.length)
          for (const c of s.citations.slice(0, 2)) {
            const ev = findEvidence(c.text);
            const cls = ev ? `evidence-link ${ev.verdict}` : "evidence-link";
            const badge = ev
              ? `<span class="evidence-badge evidence-badge-${ev.verdict === "verified" ? "verified" : ev.verdict === "partial" ? "partial" : "failed"}">${ev.verdict === "verified" ? "linked" : ev.verdict}</span>`
              : "";
            const onclick =
              ev && ev.source_start != null
                ? `onclick="showEvidence(${ev.source_start}, ${ev.source_end}, '${ev.verdict}')"`
                : "";
            h += `<div class="citation ${cls}" ${onclick}><strong>${c.source}:</strong> "${c.text.substring(0, 130)}"${badge}</div>`;
          }
        h += "</div>";
      }
    h += "</div></div>";
  }
  document.getElementById("asam-dimensions").innerHTML = h;
  let sh = "";
  if (d.loc_determination_steps)
    for (const s of d.loc_determination_steps)
      sh += `<div class="step"><strong>Step ${s.step}:</strong> ${s.description} &rarr; <em style="color:rgba(255,255,255,0.6);">${s.result}</em></div>`;
  document.getElementById("asam-steps").innerHTML = sh;
  if (d.qa_agent) {
    document.getElementById("asam-qa").classList.remove("hidden");
    renderQATerminal("asam", d.qa_agent);
  }
  document.getElementById("tab-btn-asam").classList.remove("hidden");
  showTab("asam");
  logActivity("asam", `ASAM evaluation — Level ${d.recommended_level}`);
  addEvaluation(
    "asam",
    `ASAM — Level ${d.recommended_level}`,
    d.recommended_level_name || "",
    d,
  );
}

/* ── TJC ── */
async function runTJC() {
  if (!patientId) return toast("Extract patient data first", "warning");
  const r = await fetch(`${API}/api/v1/patients/${patientId}/extract`);
  if (!r.ok)
    return toast("Patient not found in database. Re-extract first.", "error");

  document.getElementById("tab-btn-tjc").classList.remove("hidden");
  showTab("tjc");
  document.getElementById("tjc-qa").classList.remove("hidden");
  const terminal = document.getElementById("tjc-qa-terminal");
  const badge = document.getElementById("tjc-qa-badge");
  terminal.innerHTML = "";
  badge.textContent = "running...";
  badge.style.color = "#93c5fd";
  badge.style.background = "rgba(59,130,246,0.15)";

  document.getElementById("tjc-pct").textContent = "--%";
  document.getElementById("tjc-progress").style.width = "0%";
  document.getElementById("tjc-standards").innerHTML = "";
  document.getElementById("tjc-gaps").innerHTML = "";
  document.getElementById("tjc-recs").innerHTML = "";
  document.getElementById("tjc-summary").textContent = "";

  try {
    const res = await fetch(
      `${API}/api/v1/patients/${patientId}/tjc-audit/stream`,
      { method: "POST" },
    );
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      let eventType = null;
      for (const l of lines) {
        if (l.startsWith("event: ")) eventType = l.substring(7);
        else if (l.startsWith("data: ") && eventType) {
          try {
            const data = JSON.parse(l.substring(6));
            renderAgentEvent(terminal, eventType, data, "tjc");
            terminal.scrollTop = terminal.scrollHeight;

            // Render the full TJC report as soon as generation completes
            if (eventType === "initial_result" && data.audit) {
              displayTJC({ ...data.audit, qa_agent: null });
            }

            if (eventType === "complete") {
              lastTJC = {
                ...data.audit,
                source_document: data.source_document,
                linked_evidence: data.linked_evidence,
              };
              currentSourceDoc = data.source_document;
              currentLinkedEvidence = data.linked_evidence || [];
              displayTJC({
                ...data.audit,
                qa_agent: null,
                linked_evidence: data.linked_evidence,
                source_document: data.source_document,
              });

              const pct = (data.accuracy * 100).toFixed(1);
              const color =
                data.accuracy >= 0.9
                  ? "#6ee7b7"
                  : data.accuracy >= 0.7
                    ? "#fde68a"
                    : "#fca5a5";
              const bg =
                data.accuracy >= 0.9
                  ? "rgba(52,211,153,0.15)"
                  : data.accuracy >= 0.7
                    ? "rgba(251,191,36,0.15)"
                    : "rgba(248,113,113,0.15)";
              badge.textContent = `${pct}% verified`;
              badge.style.color = color;
              badge.style.background = bg;

              const c = data.claims;
              terminal.innerHTML += `<div class="qa-stats-row">
                <div class="qa-stat"><div class="qa-stat-value" style="color:${color}">${pct}%</div><div class="qa-stat-label">Accuracy</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#6ee7b7">${c.verified}</div><div class="qa-stat-label">Verified</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#93c5fd">${c.fixed}</div><div class="qa-stat-label">Fixed</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#fde68a">${c.unsupported}</div><div class="qa-stat-label">Unsupported</div></div>
                <div class="qa-stat"><div class="qa-stat-value" style="color:#fca5a5">${c.failed}</div><div class="qa-stat-label">Failed</div></div>
              </div>`;

              buildDocReport("tjc", data);
              const compPct = data.audit.overall_compliance_percentage;
              toast(
                `TJC complete — ${compPct.toFixed(1)}% compliance`,
                compPct >= 80 ? "success" : "warning",
              );
              logActivity(
                "tjc",
                `TJC audit — ${compPct.toFixed(1)}% compliance (${pct}% verified)`,
              );
              loadHistory(patientId);
            }
          } catch (e) {}
          eventType = null;
        }
      }
    }
  } catch (e) {
    toast("TJC stream error: " + e.message, "error");
  }
}

function displayTJC(d) {
  const p = d.overall_compliance_percentage;
  const c = p >= 80 ? "#6ee7b7" : p >= 50 ? "#fde68a" : "#fca5a5";
  const cb = p >= 80 ? "rgba(52,211,153," : "rgba(248,113,113,";
  document.getElementById("tjc-pct").textContent = p.toFixed(1) + "%";
  document.getElementById("tjc-pct").style.background = `${cb}0.15)`;
  document.getElementById("tjc-pct").style.borderColor = `${cb}0.3)`;
  document.getElementById("tjc-progress").style.width = p + "%";
  document.getElementById("tjc-progress").style.background = c;
  let h = "";
  for (const s of d.standards) {
    const sc =
      s.overall_status === "compliant"
        ? "pass"
        : s.overall_status === "non_compliant"
          ? "fail"
          : "partial";
    h += `<div class="dimension"><div class="dimension-header" onclick="toggleDimension(this)"><span class="dimension-name">${s.standard_id} — ${s.standard_name}</span><div><span class="status status-${sc}">${s.compliance_percentage}%</span> <span class="dimension-toggle open">&#9662;</span></div></div><div class="dimension-body">`;
    for (const f of s.findings) {
      const fc =
        f.status === "pass" ? "pass" : f.status === "fail" ? "fail" : "partial";
      h += `<div class="finding finding-${fc}"><strong>${f.element}:</strong> ${f.finding.substring(0, 220)}`;
      if (f.citations?.length)
        for (const c of f.citations.slice(0, 2)) {
          const ev = findEvidence(c.text);
          const cls = ev ? `evidence-link ${ev.verdict}` : "evidence-link";
          const badge = ev
            ? `<span class="evidence-badge evidence-badge-${ev.verdict === "verified" ? "verified" : ev.verdict === "partial" ? "partial" : "failed"}">${ev.verdict === "verified" ? "linked" : ev.verdict}</span>`
            : "";
          const onclick =
            ev && ev.source_start != null
              ? `onclick="showEvidence(${ev.source_start}, ${ev.source_end}, '${ev.verdict}')"`
              : "";
          h += `<div class="citation ${cls}" ${onclick} style="margin:4px 0;"><strong>${c.source}:</strong> "${c.text.substring(0, 120)}"${badge}</div>`;
        }
      if (f.remediation)
        h += `<div style="color:rgba(255,255,255,0.5);margin-top:3px;font-size:11px;">&rarr; ${f.remediation}</div>`;
      h += "</div>";
    }
    h += "</div></div>";
  }
  document.getElementById("tjc-standards").innerHTML = h;
  let g = "";
  for (const x of d.critical_gaps)
    g += `<div class="gap-item gap-${x.severity}"><strong>[${x.severity.toUpperCase()}]</strong> ${x.standard} ${x.element}: ${x.description}</div>`;
  document.getElementById("tjc-gaps").innerHTML = g;
  let r = "";
  for (const x of d.recommendations) r += `<li>${x}</li>`;
  document.getElementById("tjc-recs").innerHTML = r;
  document.getElementById("tjc-summary").textContent = d.audit_summary;
  if (d.qa_agent) {
    document.getElementById("tjc-qa").classList.remove("hidden");
    renderQATerminal("tjc", d.qa_agent);
  }
  document.getElementById("tab-btn-tjc").classList.remove("hidden");
  showTab("tjc");
  logActivity(
    "tjc",
    `TJC audit — ${d.overall_compliance_percentage.toFixed(1)}% compliance`,
  );
  addEvaluation(
    "tjc",
    `TJC — ${d.overall_compliance_percentage.toFixed(1)}%`,
    `${d.standards?.length || 0} standards audited`,
    d,
  );
}

/* ── Tabs ── */
function showTab(t) {
  document
    .querySelectorAll("#patient-tabs .tab")
    .forEach((x) => x.classList.remove("active"));
  ["assessment", "notes", "asam", "tjc", "report"].forEach((id) =>
    document.getElementById("tab-" + id).classList.add("hidden"),
  );
  document.getElementById("tab-" + t).classList.remove("hidden");
  document.querySelectorAll("#patient-tabs .tab").forEach((x) => {
    const txt = x.textContent.trim();
    if (
      (t === "assessment" && txt === "Assessment") ||
      (t === "notes" && txt === "Progress Notes") ||
      (t === "asam" && txt === "ASAM") ||
      (t === "tjc" && txt === "TJC Audit") ||
      (t === "report" && txt === "Report")
    )
      x.classList.add("active");
  });
}

function show(i) {
  document.getElementById(i).classList.add("active");
}
function hide(i) {
  document.getElementById(i).classList.remove("active");
}

/* ── Auto-load patients from DB on page load ── */
async function loadPatients() {
  try {
    const r = await fetch(`${API}/api/v1/patients`);
    if (!r.ok) return;
    const patients = await r.json();

    // Populate sidebar
    const list = document.getElementById("patient-list");
    if (!patients.length) {
      list.innerHTML =
        '<div style="padding:8px 12px;font-size:11px;color:rgba(255,255,255,0.15);">No patients extracted yet</div>';
    } else {
      list.innerHTML = "";
      for (const p of patients) {
        const initials = (p.first_name[0] + p.last_name[0]).toUpperCase();
        list.insertAdjacentHTML(
          "beforeend",
          `<div class="sidebar-patient" data-id="${p.id}" onclick="loadAndSelect('${p.id}')">
            <div class="sidebar-patient-avatar">${initials}</div>
            <div class="sidebar-patient-info">
              <div class="sidebar-patient-name">${p.first_name} ${p.last_name}</div>
              <div class="sidebar-patient-meta">${p.date_of_birth} | ${p.note_count} notes</div>
            </div>
          </div>`,
        );
      }
    }

    // Populate main patients grid
    const grid = document.getElementById("patients-grid");
    if (!patients.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:60px 20px;">
        <div style="font-size:16px;font-weight:600;color:rgba(255,255,255,0.3);margin-bottom:8px;">No patients yet</div>
        <div style="font-size:13px;color:rgba(255,255,255,0.2);margin-bottom:20px;">Extract patient data from SimplePractice to get started</div>
        <button class="btn btn-primary" onclick="showView('extract')">Extract Data</button>
      </div>`;
    } else {
      grid.innerHTML = "";
      for (const p of patients) {
        const initials = (p.first_name[0] + p.last_name[0]).toUpperCase();
        grid.insertAdjacentHTML(
          "beforeend",
          `<div class="patient-card" onclick="loadAndSelect('${p.id}')">
            <div class="patient-card-header">
              <div class="patient-card-avatar">${initials}</div>
              <div>
                <div class="patient-card-name">${p.first_name} ${p.last_name}</div>
                <div class="patient-card-meta">DOB: ${p.date_of_birth}</div>
              </div>
            </div>
            <div class="patient-card-stats">
              <div class="patient-card-stat"><strong>${p.note_count}</strong> notes</div>
            </div>
          </div>`,
        );
      }
    }
  } catch (e) {
    /* silent */
  }
}

async function loadAndSelect(id) {
  try {
    const r = await fetch(`${API}/api/v1/patients/${id}/extract`);
    if (!r.ok) return toast("Failed to load patient", "error");
    const d = await r.json();
    currentData = d;
    patientId = id;
    displayPatient(d);
    showView("patient");
    document
      .querySelectorAll(".sidebar-patient")
      .forEach((p) => p.classList.toggle("active", p.dataset.id === id));
    document
      .querySelectorAll(".sidebar-item")
      .forEach((i) => i.classList.remove("active"));
    // Also add note items to sidebar if not already there
    const list = document.getElementById("patient-list");
    if (!list.querySelector(`.sidebar-notes[data-patient="${id}"]`)) {
      let html = `<div class="sidebar-notes" data-patient="${id}">
        <div class="sidebar-note-item" onclick="loadAndSelect('${id}');showTab('assessment')">Assessment</div>`;
      for (const note of d.progress_notes)
        html += `<div class="sidebar-note-item" onclick="loadAndSelect('${id}');showTab('notes')">${note.note_format} - ${note.note_date}</div>`;
      html += `</div>`;
      const patientEl = list.querySelector(`[data-id="${id}"]`);
      if (patientEl) patientEl.insertAdjacentHTML("afterend", html);
    }
    loadHistory(id);
  } catch (e) {
    toast("Error loading patient: " + e.message, "error");
  }
}

// Load on page init
loadPatients();

/* ── Agent Event Renderer (Claude Code style) ── */
function renderAgentEvent(terminal, event, data, type) {
  switch (event) {
    case "agent_start":
      terminal.innerHTML += line(
        "header",
        "$",
        `<strong>${escHtml(data.message)}</strong>`,
      );
      if (data.detail)
        terminal.innerHTML += line("dim", " ", `  ${escHtml(data.detail)}`);
      break;

    case "thinking":
      terminal.innerHTML += `<div class="qa-line" style="margin:4px 0"><span class="qa-line-icon" style="color:rgba(168,85,247,0.7)">⟡</span><span class="qa-line-text" style="color:rgba(168,85,247,0.7);font-style:italic">${escHtml(data.message)}</span></div>`;
      break;

    case "tool_call": {
      const toolIcons = {
        llm_call: "⚡",
        decompose: "◇",
        verify_citations: "🔍",
        fix_claims: "🔧",
        reconstruct: "⟲",
        final_verify: "✓",
      };
      const ic = toolIcons[data.tool] || "▸";
      terminal.innerHTML += `<div class="qa-line" style="margin:3px 0"><span class="qa-line-icon">${ic}</span><span class="qa-line-text"><strong style="color:#93c5fd">${escHtml(data.tool)}</strong> ${escHtml(data.description)}</span></div>`;
      if (data.detail)
        terminal.innerHTML += line("dim", " ", `  ${escHtml(data.detail)}`);
      break;
    }

    case "tool_result":
      terminal.innerHTML += `<div class="qa-line" style="margin:2px 0"><span class="qa-line-icon" style="color:rgba(255,255,255,0.2)">↳</span><span class="qa-line-text" style="color:rgba(255,255,255,0.45)">${escHtml(data.result)}</span></div>`;
      break;

    case "claim_verified":
      terminal.innerHTML += `<div class="qa-line verified" style="margin:1px 0;padding-left:8px"><span class="qa-line-icon" style="color:#34d399">✓</span><span class="qa-line-text"><strong>${escHtml(data.location)}</strong> <span style="color:rgba(52,211,153,0.5)">(${(data.score * 100).toFixed(0)}%)</span> <span style="color:rgba(255,255,255,0.25)">"${escHtml((data.snippet || "").substring(0, 60))}"</span></span></div>`;
      break;

    case "claim_failed": {
      const fIcon =
        data.issue_type === "hallucination"
          ? "✗"
          : data.issue_type === "negation_flip"
            ? "⚠"
            : "~";
      const fColor =
        data.issue_type === "hallucination"
          ? "#f87171"
          : data.issue_type === "negation_flip"
            ? "#f87171"
            : "#fbbf24";
      terminal.innerHTML += `<div class="qa-line failed" style="margin:1px 0;padding-left:8px"><span class="qa-line-icon" style="color:${fColor}">${fIcon}</span><span class="qa-line-text" style="color:${fColor}"><strong>${escHtml(data.location)}</strong> [${escHtml(data.issue_type)}] "${escHtml((data.snippet || "").substring(0, 45))}" <span style="opacity:0.7">— ${escHtml((data.issue || "").substring(0, 70))}</span></span></div>`;
      break;
    }

    case "search":
      terminal.innerHTML += `<div class="qa-line" style="margin:1px 0;padding-left:16px"><span class="qa-line-icon" style="color:rgba(251,191,36,0.6)">↳</span><span class="qa-line-text" style="color:rgba(255,255,255,0.3)">${escHtml(data.description)}</span></div>`;
      break;

    case "claim_fixed":
      terminal.innerHTML += `<div class="qa-line fixed" style="margin:2px 0;padding-left:8px"><span class="qa-line-icon" style="color:#60a5fa">✎</span><span class="qa-line-text"><strong style="color:#60a5fa">${escHtml(data.location)}</strong> <span style="color:rgba(248,113,113,0.5);text-decoration:line-through">"${escHtml((data.old_text || "").substring(0, 40))}"</span> → <span style="color:rgba(52,211,153,0.8)">"${escHtml((data.new_text || "").substring(0, 50))}"</span></span></div>`;
      break;

    case "claim_unsupported":
      terminal.innerHTML += `<div class="qa-line unsupported" style="margin:2px 0;padding-left:8px"><span class="qa-line-icon" style="color:#fbbf24">○</span><span class="qa-line-text"><strong>${escHtml(data.location)}</strong> — ${escHtml(data.reason || "no evidence in source")}</span></div>`;
      break;

    case "verify_summary": {
      const pct = (data.accuracy * 100).toFixed(0);
      const vc =
        data.verified >= data.total * 0.9
          ? "#34d399"
          : data.verified >= data.total * 0.7
            ? "#fbbf24"
            : "#f87171";
      terminal.innerHTML += `<div style="margin:6px 0 4px 0;padding:6px 12px;background:rgba(255,255,255,0.03);border-radius:8px;font-size:11px;display:flex;gap:16px;align-items:center"><span style="color:${vc};font-weight:700">${pct}%</span><span style="color:rgba(52,211,153,0.7)">✓ ${data.verified} verified</span>${data.failed ? `<span style="color:rgba(248,113,113,0.7)">✗ ${data.failed} failed</span>` : ""}${data.unsupported ? `<span style="color:rgba(251,191,36,0.7)">○ ${data.unsupported} unsupported</span>` : ""}<span style="color:rgba(255,255,255,0.2)">of ${data.total} claims</span></div>`;
      break;
    }

    case "llm_stream_start": {
      const labels = {
        clinical_reasoning: "Chain of Thought",
        json_output: "Structured Output",
        fix_claims: "Finding Evidence",
        reconstruct: "Rebuilding",
      };
      const lbl = labels[data.label] || data.label;
      const passLabel = data.pass ? ` (Pass ${data.pass}/2)` : "";
      terminal.innerHTML += `<div class="qa-stream-block" id="stream-${data.pass || data.label}" style="margin:10px 0"><div style="color:rgba(147,197,253,0.7);font-size:12px;font-weight:600;margin:0 0 6px;display:flex;align-items:center;gap:8px"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:rgba(147,197,253,0.5)"></span>${lbl}${passLabel}</div><pre style="font-family:'SF Mono',Consolas,monospace;font-size:12px;color:rgba(255,255,255,0.5);white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto;padding:14px 16px;background:rgba(0,0,0,0.3);border-radius:10px;margin:0 0 8px;line-height:1.65;border:1px solid rgba(255,255,255,0.06)"></pre></div>`;
      break;
    }

    case "llm_token": {
      const blockId = `stream-${data.pass || data.label}`;
      const pre = document.querySelector(`#${blockId} pre`);
      if (pre) {
        pre.textContent += data.text;
        pre.scrollTop = pre.scrollHeight;
      }
      // Don't auto-scroll the whole terminal for every token — too janky
      return;
    }

    case "llm_stream_end": {
      const blockId = `stream-${data.pass || data.label}`;
      const block = document.getElementById(blockId);
      if (block) {
        const pre = block.querySelector("pre");
        if (pre && data.label === "json_output") {
          pre.style.maxHeight = "150px";
          pre.style.opacity = "0.35";
          pre.style.transition = "all 0.3s";
        }
      }
      break;
    }

    case "iteration":
      if (data.phase === "start")
        terminal.innerHTML += `<div style="margin:10px 0 4px 0;padding:4px 0;border-top:1px solid rgba(255,255,255,0.06)"><div class="qa-line header"><span class="qa-line-icon">▸</span><span class="qa-line-text"><strong>${escHtml(data.message)}</strong></span></div></div>`;
      else if (data.phase === "complete")
        terminal.innerHTML += line("dim", " ", `  ${escHtml(data.message)}`);
      break;
  }
}

/* ── QA Agent Terminal Renderer (fallback for non-streamed) ── */
function renderQATerminal(type, qa) {
  const terminal = document.getElementById(`${type}-qa-terminal`);
  const badge = document.getElementById(`${type}-qa-badge`);
  const pct = (qa.accuracy * 100).toFixed(1);
  const c = qa.claims;

  const color =
    qa.accuracy >= 0.9 ? "#6ee7b7" : qa.accuracy >= 0.7 ? "#fde68a" : "#fca5a5";
  const bg =
    qa.accuracy >= 0.9
      ? "rgba(52,211,153,0.15)"
      : qa.accuracy >= 0.7
        ? "rgba(251,191,36,0.15)"
        : "rgba(248,113,113,0.15)";
  badge.textContent = `${pct}% verified`;
  badge.style.color = color;
  badge.style.background = bg;

  let html = "";
  html += line("header", ">", `QA Agent — ${c.total} claims extracted`);
  html += line("dim", " ", "");

  // Trace each iteration
  for (const iter of qa.trace) {
    html += line(
      "header",
      "~",
      `Iteration ${iter.iteration}${iter.iteration === 0 ? " (initial generation)" : ""}`,
    );
    html += line(
      "verified",
      "+",
      `${iter.verified} claims verified against source`,
    );

    if (iter.pending > 0)
      html += line("failed", "!", `${iter.pending} claims failed verification`);
    if (iter.unsupported > 0)
      html += line(
        "unsupported",
        "?",
        `${iter.unsupported} claims unsupported by source`,
      );

    // Show specific issues
    if (iter.issues) {
      for (const issue of iter.issues.slice(0, 8)) {
        const icon =
          issue.type === "hallucination"
            ? "x"
            : issue.type === "negation_flip"
              ? "!"
              : issue.type === "weak_match"
                ? "~"
                : "?";
        const cls =
          issue.type === "hallucination"
            ? "failed"
            : issue.type === "negation_flip"
              ? "failed"
              : "unsupported";
        html += line(
          cls,
          icon,
          `<strong>[${issue.type}]</strong> ${escHtml(issue.id)}: ${escHtml((issue.issue || "").substring(0, 120))}`,
        );
      }
      if (iter.issues.length > 8)
        html += line("dim", " ", `... and ${iter.issues.length - 8} more`);
    }

    // Show fixes
    if (iter.fixes_applied > 0)
      html += line("fixed", "*", `${iter.fixes_applied} claims fixed by agent`);
    if (iter.still_broken > 0)
      html += line("failed", "x", `${iter.still_broken} claims still broken`);
    if (iter.marked_unsupported > 0)
      html += line(
        "unsupported",
        "-",
        `${iter.marked_unsupported} claims marked unsupported`,
      );

    html += line("dim", " ", "");
  }

  // Unresolved claims
  if (qa.unresolved_claims?.length > 0) {
    html += line(
      "header",
      "!",
      `Unresolved claims (${qa.unresolved_claims.length}):`,
    );
    for (const claim of qa.unresolved_claims.slice(0, 10)) {
      const cls =
        claim.verdict === "unsupported"
          ? "unsupported"
          : claim.verdict === "fixed"
            ? "fixed"
            : "failed";
      const icon =
        claim.verdict === "unsupported"
          ? "?"
          : claim.verdict === "fixed"
            ? "*"
            : "x";
      html += line(
        cls,
        icon,
        `<strong>${escHtml(claim.location)}</strong> [${claim.verdict}] ${escHtml((claim.issue || "").substring(0, 100))}`,
      );
    }
    if (qa.unresolved_claims.length > 10)
      html += line(
        "dim",
        " ",
        `... and ${qa.unresolved_claims.length - 10} more`,
      );
    html += line("dim", " ", "");
  }

  // Final summary
  html += line("header", ">", "Final Results");
  html += `<div class="qa-stats-row">
    <div class="qa-stat"><div class="qa-stat-value" style="color:${color}">${pct}%</div><div class="qa-stat-label">Accuracy</div></div>
    <div class="qa-stat"><div class="qa-stat-value" style="color:#6ee7b7">${c.verified}</div><div class="qa-stat-label">Verified</div></div>
    <div class="qa-stat"><div class="qa-stat-value" style="color:#93c5fd">${c.fixed}</div><div class="qa-stat-label">Fixed</div></div>
    <div class="qa-stat"><div class="qa-stat-value" style="color:#fde68a">${c.unsupported}</div><div class="qa-stat-label">Unsupported</div></div>
    <div class="qa-stat"><div class="qa-stat-value" style="color:#fca5a5">${c.failed}</div><div class="qa-stat-label">Failed</div></div>
    <div class="qa-stat"><div class="qa-stat-value" style="color:rgba(255,255,255,0.5)">${qa.iterations}</div><div class="qa-stat-label">Iterations</div></div>
  </div>`;

  terminal.innerHTML = html;
}

function line(cls, icon, text) {
  return `<div class="qa-line ${cls}"><span class="qa-line-icon">${escHtml(icon)}</span><span class="qa-line-text">${text}</span></div>`;
}

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

/* ── Linked Evidence ── */
function findEvidence(citedText) {
  if (!currentLinkedEvidence.length) return null;
  const ct = (citedText || "")
    .toLowerCase()
    .trim()
    .replace(/^["']+|["']+$/g, "");
  return (
    currentLinkedEvidence.find((e) => {
      const et = (e.cited_text || "")
        .toLowerCase()
        .trim()
        .replace(/^["']+|["']+$/g, "");
      return (
        et === ct ||
        ct.startsWith(et.substring(0, 40)) ||
        et.startsWith(ct.substring(0, 40))
      );
    }) || null
  );
}

function _findSectionTitle(pos) {
  if (!currentSourceDoc) return null;
  const prefix = currentSourceDoc.substring(0, pos);
  const match = prefix.match(/===\s*([^=]+?)\s*===/g);
  if (!match) return null;
  const last = match[match.length - 1];
  return last.replace(/^===\s*|\s*===$/g, "").trim();
}

function showEvidence(start, end, verdict) {
  if (!currentSourceDoc) return;
  const viewer = document.getElementById("source-viewer");
  const body = document.getElementById("source-viewer-body");
  const title = document.getElementById("source-viewer-title");

  // Find which section this evidence comes from
  const sectionName = _findSectionTitle(start);

  // Build the source text with the matched region highlighted
  const before = escHtml(
    currentSourceDoc.substring(Math.max(0, start - 300), start),
  );
  const match = escHtml(currentSourceDoc.substring(start, end));
  const after = escHtml(
    currentSourceDoc.substring(
      end,
      Math.min(currentSourceDoc.length, end + 300),
    ),
  );

  const hlClass =
    verdict === "verified"
      ? "source-highlight source-highlight-verified"
      : verdict === "partial"
        ? "source-highlight"
        : "source-highlight source-highlight-failed";

  body.innerHTML = `${before}<span class="${hlClass}" id="evidence-target">${match}</span>${after}`;
  const verdictLabel =
    verdict === "verified"
      ? "Verified"
      : verdict === "partial"
        ? "Partial Match"
        : "Not Found";
  title.textContent = sectionName
    ? `${sectionName} — ${verdictLabel}`
    : `Linked Evidence — ${verdictLabel}`;
  viewer.classList.add("open");

  // Scroll to highlighted text
  setTimeout(() => {
    const target = document.getElementById("evidence-target");
    if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 100);
}

function closeSourceViewer() {
  document.getElementById("source-viewer").classList.remove("open");
}

/* ── Interactive Chat ── */
let chatHistory = { asam: [], tjc: [] };

async function sendChat(type) {
  const input = document.getElementById(`${type}-chat-input`);
  const terminal = document.getElementById(`${type}-qa-terminal`);
  const message = input.value.trim();
  if (!message || !patientId) return;

  input.value = "";

  // Show user message
  terminal.innerHTML += `<div class="chat-msg chat-msg-user"><strong>You:</strong> ${escHtml(message)}</div>`;
  terminal.scrollTop = terminal.scrollHeight;

  // Add to history
  chatHistory[type].push({ role: "user", content: message });

  // Create assistant response container
  const msgId = `chat-resp-${Date.now()}`;
  terminal.innerHTML += `<div class="chat-msg chat-msg-assistant" id="${msgId}"></div>`;
  terminal.scrollTop = terminal.scrollHeight;

  // Get current evaluation/audit data
  const evalData = type === "asam" ? lastASAM : lastTJC;

  try {
    const res = await fetch(`${API}/api/v1/patients/${patientId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        context_type: type,
        evaluation_json: evalData || null,
        history: chatHistory[type].slice(0, -1), // exclude current message (it's in 'message')
      }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullResponse = "";
    const responseEl = document.getElementById(msgId);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.substring(6);
          if (data === "[DONE]") continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.text) {
              fullResponse += parsed.text;
              responseEl.textContent = fullResponse;
              terminal.scrollTop = terminal.scrollHeight;
            }
          } catch (e) {}
        }
      }
    }

    // Save to history
    chatHistory[type].push({ role: "assistant", content: fullResponse });
  } catch (e) {
    document.getElementById(msgId).textContent = `Error: ${e.message}`;
  }
}

/* ── Doc-Style Report Builder ── */
function buildDocReport(type, data) {
  const el = document.getElementById("report-content");
  document.getElementById("tab-btn-report").classList.remove("hidden");

  if (type === "asam") {
    const d = data.evaluation || data;
    const patient = currentData?.patient;
    const name = patient
      ? `${patient.first_name} ${patient.last_name}`
      : "Patient";

    let html = `<h1>ASAM Level of Care Assessment</h1>`;
    html += `<div class="doc-meta">${name} | ${patient?.date_of_birth || ""} | Generated ${new Date().toLocaleDateString()}</div>`;
    html += `<div class="doc-legend"><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#34d399"></div> Verified in source</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#fbbf24"></div> Partial match</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#f87171"></div> Not found in source</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:rgba(255,255,255,0.15)"></div> No citation</div></div>`;

    html += `<p><strong>Recommended Level of Care:</strong> ${wrapSentence(`Level ${d.recommended_level} — ${d.recommended_level_name}`, null)}</p>`;
    if (d.level_rationale)
      html += `<p>${wrapSentence(d.level_rationale, null)}</p>`;

    for (const dim of d.dimensions || []) {
      html += `<h2>Dimension ${dim.dimension_number}: ${dim.dimension_name}</h2>`;
      for (const sub of dim.subdimensions || []) {
        html += `<h3>${sub.name} — Risk: ${sub.risk_rating_code} → ${sub.minimum_level}</h3>`;
        html += `<p>${wrapWithEvidence(sub.rationale, sub.citations)}</p>`;
      }
    }

    if (d.loc_determination_steps?.length) {
      html += `<h2>Level of Care Determination</h2>`;
      for (const step of d.loc_determination_steps) {
        html += `<p><strong>Step ${step.step}:</strong> ${step.description} — ${wrapSentence(step.result, null)}</p>`;
      }
    }

    html += `<h2>Clinical Summary</h2>`;
    html += `<p>${wrapSentence(d.clinical_summary || "", null)}</p>`;

    if (d.dimension_6_notes) {
      html += `<h2>Dimension 6: Person-Centered Considerations</h2>`;
      html += `<p>${wrapSentence(d.dimension_6_notes, null)}</p>`;
    }

    el.innerHTML = html;
  } else if (type === "tjc") {
    const d = data.audit || data;
    const patient = currentData?.patient;
    const name = patient
      ? `${patient.first_name} ${patient.last_name}`
      : "Patient";

    let html = `<h1>TJC Compliance Audit Report</h1>`;
    html += `<div class="doc-meta">${name} | ${patient?.date_of_birth || ""} | Overall Compliance: ${d.overall_compliance_percentage?.toFixed(1)}% | Generated ${new Date().toLocaleDateString()}</div>`;
    html += `<div class="doc-legend"><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#34d399"></div> Verified in source</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#fbbf24"></div> Partial match</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:#f87171"></div> Not found</div><div class="doc-legend-item"><div class="doc-legend-swatch" style="background:rgba(255,255,255,0.15)"></div> No citation</div></div>`;

    for (const std of d.standards || []) {
      html += `<h2>${std.standard_id}: ${std.standard_name} (${std.compliance_percentage?.toFixed(0)}%)</h2>`;
      for (const f of std.findings || []) {
        const statusIcon =
          f.status === "pass"
            ? '<span style="color:#34d399">PASS</span>'
            : f.status === "fail"
              ? '<span style="color:#f87171">FAIL</span>'
              : '<span style="color:#fbbf24">PARTIAL</span>';
        html += `<h3>${f.element} — ${statusIcon}</h3>`;
        html += `<p>${wrapWithEvidence(f.finding, f.citations)}</p>`;
        if (f.remediation)
          html += `<p style="color:rgba(251,191,36,0.7);font-size:13px">Remediation: ${escHtml(f.remediation)}</p>`;
      }
    }

    if (d.critical_gaps?.length) {
      html += `<h2>Critical Gaps</h2>`;
      for (const g of d.critical_gaps) {
        html += `<p><strong style="color:#f87171">[${g.severity.toUpperCase()}]</strong> ${g.standard} ${g.element}: ${escHtml(g.description)}</p>`;
      }
    }

    html += `<h2>Summary</h2>`;
    html += `<p>${wrapSentence(d.audit_summary || "", null)}</p>`;

    el.innerHTML = html;
  }
}

function wrapWithEvidence(text, citations) {
  if (!text) return "";
  // Split the text into sentences, then for each citation wrap the matching part
  let result = escHtml(text);

  if (citations?.length) {
    for (const c of citations) {
      const ev = findEvidence(c.text);
      const verdict = ev?.verdict || "unverified";
      const score = ev?.score ? (ev.score * 100).toFixed(0) + "%" : "";
      const start = ev?.source_start;
      const end = ev?.source_end;
      const onclick =
        start != null
          ? `onclick="showEvidence(${start}, ${end}, '${verdict}')"`
          : "";
      const tooltipText =
        verdict === "verified"
          ? `Verified in source (${score})`
          : verdict === "partial"
            ? `Partial match (${score})`
            : verdict === "not_found"
              ? "Not found in source — possible hallucination"
              : "No verification data";
      const sourceSnippet = ev?.source_text
        ? escHtml(ev.source_text.substring(0, 80))
        : "";

      // Wrap the cited quote inline
      const quoteSafe = escHtml(c.text.substring(0, 80));
      const span = `<span class="doc-sentence ${verdict}" ${onclick}>"${quoteSafe}"<span class="doc-tooltip"><strong>${verdict.toUpperCase()}</strong> ${score ? "— " + score + " match" : ""}<br>${sourceSnippet ? 'Source: "' + sourceSnippet + '..."' : "Click to view source"}</span></span>`;

      result += `<br><span style="font-size:12px;color:rgba(255,255,255,0.3);margin-left:8px">${escHtml(c.source)}: ${span}</span>`;
    }
  }

  return result;
}

function wrapSentence(text, evidence) {
  if (!text) return "";
  return escHtml(text);
}

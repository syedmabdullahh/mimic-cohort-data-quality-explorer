/* =====================================================================
   MIMIC-IV Cohort & Data Quality Explorer — App Logic v3.0
   Clean rewrite — no optional chaining, fully browser-compatible
   ===================================================================== */

document.addEventListener("DOMContentLoaded", function() {

  /* ------------------------------------------------------------------
     API BASE URL
  ------------------------------------------------------------------ */
  var origin = window.location.origin;
  if (!origin || origin === "null" || origin.indexOf("file") === 0) {
    origin = "http://127.0.0.1:8000";
  }
  var API_BASE = origin + "/api";

  /* ------------------------------------------------------------------
     STATE
  ------------------------------------------------------------------ */
  var cohortChart = null;
  var labChart = null;
  var riskDonutChart = null;
  var qualityBreakdownChart = null;
  var reviewQueue = [];
  var currentFilter = "all";
  var cachedScores = null;
  var cachedIssues = { baseline: [], ai: [] };

  /* ------------------------------------------------------------------
     LIVE CLOCK
  ------------------------------------------------------------------ */
  function updateClock() {
    var el = document.getElementById("live-clock");
    if (el) el.textContent = new Date().toLocaleTimeString("en-US", { hour12: false });
  }
  updateClock();
  setInterval(updateClock, 1000);

  /* ------------------------------------------------------------------
     TOAST NOTIFICATIONS
  ------------------------------------------------------------------ */
  function showToast(message, type, duration) {
    type = type || "info";
    duration = duration || 4000;
    var container = document.getElementById("toast-container");
    if (!container) return;
    var icons = { success: "fa-circle-check", error: "fa-circle-xmark", info: "fa-circle-info", warning: "fa-triangle-exclamation" };
    var toast = document.createElement("div");
    toast.className = "toast " + type;
    toast.innerHTML = '<i class="fa-solid ' + (icons[type] || icons.info) + ' toast-icon"></i><span>' + message + "</span>";
    container.appendChild(toast);
    setTimeout(function() {
      toast.classList.add("hide");
      setTimeout(function() { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 300);
    }, duration);
  }

  /* ------------------------------------------------------------------
     COUNT-UP ANIMATION
  ------------------------------------------------------------------ */
  function animateCountUp(el, target, suffix, duration) {
    if (!el) return;
    suffix = suffix || "";
    duration = duration || 900;
    var num = parseFloat(target);
    if (isNaN(num)) { el.textContent = target + suffix; return; }
    var startTime = null;
    var isFloat = String(target).indexOf(".") !== -1;
    function step(currentTime) {
      if (!startTime) startTime = currentTime;
      var progress = Math.min((currentTime - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = num * eased;
      el.textContent = (isFloat ? value.toFixed(1) : Math.round(value)) + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ------------------------------------------------------------------
     SCORE RING ANIMATION
  ------------------------------------------------------------------ */
  function animateRing(fillEl, score) {
    if (!fillEl) return;
    var circumference = 2 * Math.PI * 54;
    var offset = circumference - (score / 100) * circumference;
    setTimeout(function() { fillEl.style.strokeDashoffset = offset; }, 200);
  }

  /* ------------------------------------------------------------------
     BUTTON LOADING STATE
  ------------------------------------------------------------------ */
  function setLoading(btn, isLoading, originalHTML) {
    if (!btn) return;
    if (isLoading) {
      btn.disabled = true;
      btn.dataset.orig = btn.innerHTML;
      btn.innerHTML = '<span class="loading-spinner"></span> Running&hellip;';
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHTML || btn.dataset.orig || btn.innerHTML;
    }
  }

  /* ------------------------------------------------------------------
     SAFE ELEMENT GETTER
  ------------------------------------------------------------------ */
  function el(id) { return document.getElementById(id); }
  function qs(sel) { return document.querySelector(sel); }

  /* ------------------------------------------------------------------
     TAB NAVIGATION
  ------------------------------------------------------------------ */
  var navItems = document.querySelectorAll(".nav-item");
  var tabPanes = document.querySelectorAll(".tab-pane");

  navItems.forEach(function(item) {
    item.addEventListener("click", function() {
      navItems.forEach(function(n) { n.classList.remove("active"); });
      tabPanes.forEach(function(p) { p.classList.remove("active"); });
      item.classList.add("active");
      var targetId = item.getAttribute("data-tab");
      var pane = el(targetId);
      if (pane) pane.classList.add("active");
      if (targetId === "tab-reports" && cachedScores) {
        populateReportsTab(cachedScores);
      }
    });
  });

  /* ------------------------------------------------------------------
     FILTER TABS (Review Workspace)
  ------------------------------------------------------------------ */
  document.querySelectorAll(".filter-tab").forEach(function(tab) {
    tab.addEventListener("click", function() {
      document.querySelectorAll(".filter-tab").forEach(function(t) { t.classList.remove("active"); });
      tab.classList.add("active");
      currentFilter = tab.getAttribute("data-filter");
      renderQueueCards();
    });
  });

  /* ------------------------------------------------------------------
     PRESET QUERIES
  ------------------------------------------------------------------ */
  window.setQuery = function(q) {
    var input = el("cohort-query-input");
    if (input) { input.value = q; el("btn-run-query").click(); }
  };

  /* ------------------------------------------------------------------
     CONFIDENCE SLIDER
  ------------------------------------------------------------------ */
  var confSlider = el("conf-slider");
  if (confSlider) {
    confSlider.addEventListener("input", function(e) {
      var confVal = el("conf-val");
      if (confVal) confVal.textContent = parseFloat(e.target.value).toFixed(2);
      runAIChecks();
    });
  }

  /* ------------------------------------------------------------------
     LAB DROPDOWN
  ------------------------------------------------------------------ */
  var labSelect = el("lab-item-select");
  if (labSelect) {
    labSelect.addEventListener("change", function(e) { fetchLabDistribution(e.target.value); });
  }

  /* ------------------------------------------------------------------
     BUTTON BINDINGS
  ------------------------------------------------------------------ */
  function bindBtn(id, fn) {
    var b = el(id);
    if (b) b.addEventListener("click", fn);
  }
  bindBtn("btn-demo-mode", runOneClickDemo);
  bindBtn("btn-download-pdf-sidebar", downloadPDFReport);
  bindBtn("btn-download-pdf-reports", downloadPDFReport);
  bindBtn("btn-run-query", runCohortQuery);
  bindBtn("btn-run-baseline", runBaselineChecks);
  bindBtn("btn-run-ai", runAIChecks);
  bindBtn("btn-send-to-queue", sendFlagsToQueue);
  bindBtn("btn-run-eval", runMetricEvaluation);

  /* ------------------------------------------------------------------
     JSON TOGGLE BUTTON (Ground Truth)
  ------------------------------------------------------------------ */
  var toggleJsonBtn = el("btn-toggle-json");
  if (toggleJsonBtn) {
    toggleJsonBtn.addEventListener("click", function() {
      var box = el("eval-seeds-json");
      if (!box) return;
      if (box.classList.contains("hidden")) {
        box.classList.remove("hidden");
        toggleJsonBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Hide Raw JSON';
      } else {
        box.classList.add("hidden");
        toggleJsonBtn.innerHTML = '<i class="fa-solid fa-code"></i> View Raw JSON';
      }
    });
  }

  /* ------------------------------------------------------------------
     INITIAL DATA LOAD
  ------------------------------------------------------------------ */
  fetchInfo();
  fetchQualityScores();
  fetchLabDistribution(null);
  fetchExecutiveInsights();
  runAIChecks();
  runBaselineChecks();

  /* ==================================================================
     API FUNCTIONS
  ================================================================== */

  function fetchInfo() {
    fetch(API_BASE + "/info")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var wsPath = el("ws-path-text");
        if (wsPath) wsPath.textContent = data.data_dir || "—";
        var totalCount = el("metric-total-count");
        if (totalCount) totalCount.textContent = data.total_patients || 0;
        var kpiPat = el("kpi-total-patients");
        if (kpiPat) animateCountUp(kpiPat, data.total_patients || 0, "", 900);
        var pBar = el("kpi-patients-bar");
        if (pBar) setTimeout(function() { pBar.style.width = "100%"; }, 300);
        var statusBadge = el("data-status-badge");
        if (statusBadge) {
          var label = data.is_synthetic ? "Synthetic Dataset" : "Real MIMIC-IV Demo";
          statusBadge.innerHTML = '<span class="status-dot"></span> ' + label;
        }
      })
      .catch(function(e) { console.error("fetchInfo error:", e); });
  }

  function fetchQualityScores() {
    fetch(API_BASE + "/quality/scores")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        cachedScores = data;
        var heroScoreEl = el("hero-score-val");
        if (heroScoreEl) animateCountUp(heroScoreEl, Math.round(data.overall_score), "", 900);
        animateRing(el("hero-ring-fill"), data.overall_score);
        setScoreCard("score-overall",   data.overall_score,       "bar-overall");
        setScoreCard("score-missing",   data.missing_data_score,  "bar-missing");
        setScoreCard("score-duplicate", data.duplicate_score,     "bar-duplicate");
        setScoreCard("score-temporal",  data.temporal_score,      "bar-temporal");
        setScoreCard("score-outlier",   data.outlier_score,       "bar-outlier");
        var kpiTrust = el("kpi-trust-score");
        if (kpiTrust) animateCountUp(kpiTrust, Math.round(data.overall_score), "", 900);
        var kpiTrustBar = el("kpi-trust-bar");
        if (kpiTrustBar) setTimeout(function() { kpiTrustBar.style.width = data.overall_score + "%"; }, 300);
        var kpiTrustTrend = el("kpi-trust-trend");
        if (kpiTrustTrend) {
          if (data.overall_score >= 80) {
            kpiTrustTrend.className = "kpi-trend up";
            kpiTrustTrend.innerHTML = '<i class="fa-solid fa-arrow-up"></i> Good health';
          } else if (data.overall_score >= 60) {
            kpiTrustTrend.className = "kpi-trend flat";
            kpiTrustTrend.innerHTML = '<i class="fa-solid fa-minus"></i> Moderate quality';
          } else {
            kpiTrustTrend.className = "kpi-trend down";
            kpiTrustTrend.innerHTML = '<i class="fa-solid fa-arrow-down"></i> Needs attention';
          }
        }
        renderQualityBreakdownChart(data);
        var repTab = el("tab-reports");
        if (repTab && repTab.classList.contains("active")) populateReportsTab(data);
      })
      .catch(function(e) { console.error("fetchQualityScores error:", e); });
  }

  function setScoreCard(elId, score, barId) {
    var rounded = Math.round(score || 0);
    var scoreEl = el(elId);
    if (scoreEl) animateCountUp(scoreEl, rounded, " / 100", 900);
    var barEl = el(barId);
    if (barEl) setTimeout(function() { barEl.style.width = (score || 0) + "%"; }, 400);
  }

  function fetchExecutiveInsights() {
    var container = el("exec-findings-container");
    var countEl = el("exec-findings-count");
    fetch(API_BASE + "/executive/insights")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (countEl) countEl.textContent = (data.total_issues || 0) + " Flags";
        if (!container) return;
        container.innerHTML = "";
        var items = data.top_issues || data.high_priority_issues || [];
        if (items.length === 0) {
          container.innerHTML = '<div class="empty-state" style="padding:16px 0"><span class="empty-icon"><i class="fa-solid fa-circle-check" style="color:var(--green);font-size:2rem"></i></span><p>No high-priority issues detected.</p></div>';
          return;
        }
        items.slice(0, 4).forEach(function(issue) {
          var div = document.createElement("div");
          div.className = "issue-card";
          div.innerHTML = '<div class="issue-card-header"><div class="issue-card-left"><span class="' + getRiskClass(issue.risk_level) + '">' + getRiskIcon(issue.risk_level) + " " + (issue.risk_level || "Medium") + '</span><span class="issue-card-title">' + (issue.type || "Issue") + '</span><span class="issue-card-table">' + (issue.table || "") + '</span></div><div class="issue-card-right"><span class="conf-badge">' + Math.round((issue.confidence || 0) * 100) + '% conf.</span></div></div><div class="issue-card-body">' + (issue.detail || "") + "</div>";
          container.appendChild(div);
        });
        var highRisk = items.filter(function(i) { var l = (i.risk_level || "").toLowerCase(); return l === "critical" || l === "high"; }).length;
        var kpiHR = el("kpi-high-risk");
        if (kpiHR) animateCountUp(kpiHR, highRisk, "", 900);
        var kpiHRBar = el("kpi-risk-bar");
        if (kpiHRBar) setTimeout(function() { kpiHRBar.style.width = Math.min(highRisk * 15, 100) + "%"; }, 300);
        renderRiskDonutChart(items);
      })
      .catch(function(e) {
        console.error("fetchExecutiveInsights error:", e);
        if (container) container.innerHTML = '<div class="empty-state" style="padding:16px 0"><p class="text-dim text-sm">Run AI Scanner to populate.</p></div>';
        if (countEl) countEl.textContent = "—";
      });
  }

  function runOneClickDemo() {
    var demoBtn = el("btn-demo-mode");
    setLoading(demoBtn, true);
    runCohortQuery();
    setTimeout(function() { runAIChecks(); }, 200);
    setTimeout(function() { runBaselineChecks(); }, 400);
    setTimeout(function() { fetchQualityScores(); }, 600);
    setTimeout(function() { fetchExecutiveInsights(); }, 800);
    setTimeout(function() { runMetricEvaluation(); }, 1000);
    setTimeout(function() { sendFlagsToQueue(); }, 1200);
    setTimeout(function() {
      var qualityTabBtn = qs('[data-tab="tab-quality"]');
      if (qualityTabBtn) qualityTabBtn.click();
      showToast("One-Click Judge Demo complete! All scans, scores, and queues populated.", "success", 6000);
      setLoading(demoBtn, false, '<i class="fa-solid fa-bolt-lightning"></i> <span>1-Click Judge Demo</span>');
    }, 3000);
  }

  function runCohortQuery() {
    var input = el("cohort-query-input");
    if (!input || !input.value) return;
    var btn = el("btn-run-query");
    var origHtml = btn ? btn.innerHTML : "";
    setLoading(btn, true);
    fetch(API_BASE + "/cohort/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: input.value })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var matchedEl = el("metric-matched-count");
        if (matchedEl) animateCountUp(matchedEl, data.matched_count || 0, "", 900);
        var totalEl = el("metric-total-count");
        if (totalEl) animateCountUp(totalEl, data.total_patients || 0, "", 900);
        var rate = data.total_patients > 0 ? ((data.matched_count / data.total_patients) * 100) : 0;
        var rateEl = el("metric-inclusion-rate");
        if (rateEl) animateCountUp(rateEl, rate, "%", 900);

        var clauseList = el("clause-list-container");
        if (clauseList) {
          clauseList.innerHTML = "";
          if (data.clauses && data.clauses.length > 0) {
            data.clauses.forEach(function(clause, idx) {
              var count = (data.clause_counts && data.clause_counts[clause]) || 0;
              var li = document.createElement("li");
              li.className = "clause-item";
              li.innerHTML = '<span class="clause-num">' + (idx + 1) + '</span><span class="clause-text"><strong>' + clause + '</strong></span><span class="clause-count">' + count + " pts</span>";
              clauseList.appendChild(li);
            });
            renderCohortChart(data.clauses, data.clause_counts || {});
          } else {
            clauseList.innerHTML = '<li class="clause-item"><span class="clause-num">?</span><span class="clause-text text-muted">No recognized clauses. Try \'age over 65\' or \'diagnosis of sepsis\'.</span></li>';
          }
        }

        var unmatchedBox = el("unmatched-warning");
        var unmatchedText = el("unmatched-text");
        if (unmatchedBox && unmatchedText) {
          if (data.unmatched && data.unmatched.length > 0) {
            unmatchedBox.classList.remove("hidden");
            unmatchedText.textContent = 'Unparsed tokens ignored: "' + data.unmatched[0] + '"';
          } else {
            unmatchedBox.classList.add("hidden");
          }
        }

        var tbody = qs("#cohort-results-table tbody");
        var countPill = el("cohort-table-count");
        if (tbody) {
          tbody.innerHTML = "";
          if (data.patients && data.patients.length > 0) {
            if (countPill) countPill.textContent = data.patients.length + " rows";
            data.patients.forEach(function(p) {
              var tr = document.createElement("tr");
              tr.innerHTML = '<td class="td-mono">' + p.subject_id + '</td><td><span class="pill ' + (p.gender === "F" ? "pill-purple" : "pill-cyan") + '" style="font-size:0.72rem">' + (p.gender || "N/A") + '</span></td><td class="font-bold">' + (p.anchor_age || "N/A") + '</td><td class="td-muted">' + (p.anchor_year || "N/A") + '</td><td>' + (p.dod ? '<span class="pill pill-red" style="font-size:0.7rem">' + p.dod + "</span>" : '<span class="text-green text-xs">Alive</span>') + "</td>";
              tbody.appendChild(tr);
            });
          } else {
            if (countPill) countPill.textContent = "0 rows";
            tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">No matching patients found.</td></tr>';
          }
        }
        showToast("Cohort query returned " + (data.matched_count || 0) + " patient(s)", "success");
      })
      .catch(function(e) {
        console.error("runCohortQuery error:", e);
        showToast("Cohort query failed — is the server running?", "error");
      })
      .finally(function() { setLoading(btn, false, origHtml); });
  }

  function runBaselineChecks() {
    var btn = el("btn-run-baseline");
    var origHtml = btn ? btn.innerHTML : "";
    setLoading(btn, true);
    fetch(API_BASE + "/quality/baseline")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        cachedIssues.baseline = data.issues || [];
        var bCount = el("baseline-count");
        if (bCount) bCount.textContent = (data.count || 0) + " Flags";
        var tbody = qs("#baseline-table tbody");
        if (tbody) {
          tbody.innerHTML = "";
          if (data.issues && data.issues.length > 0) {
            data.issues.forEach(function(iss) {
              var tr = document.createElement("tr");
              tr.innerHTML = '<td><span class="font-mono text-cyan text-xs">' + iss.table + '</span></td><td><span class="pill pill-grey" style="font-size:0.72rem">' + iss.type + '</span></td><td class="text-sm text-muted">' + iss.detail + "</td>";
              tbody.appendChild(tr);
            });
            renderClinicalExplainer(data.issues);
          } else {
            tbody.innerHTML = '<tr><td colspan="3" class="empty-cell">No baseline issues found.</td></tr>';
          }
        }
        showToast("Baseline check complete: " + (data.count || 0) + " flag(s) found.", "info");
      })
      .catch(function(e) {
        console.error("runBaselineChecks error:", e);
        showToast("Baseline check failed.", "error");
      })
      .finally(function() { setLoading(btn, false, origHtml); });
  }

  function runAIChecks() {
    var slider = el("conf-slider");
    var minConf = slider ? parseFloat(slider.value) : 0.4;
    var btn = el("btn-run-ai");
    var origHtml = btn ? btn.innerHTML : "";
    setLoading(btn, true);
    fetch(API_BASE + "/quality/ai?min_confidence=" + minConf)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        cachedIssues.ai = data.issues || [];
        var aiCount = el("ai-count");
        if (aiCount) aiCount.textContent = (data.filtered_count || 0) + " Flags";
        var kpiIssues = el("kpi-total-issues");
        if (kpiIssues) animateCountUp(kpiIssues, (cachedIssues.baseline.length || 0) + (data.filtered_count || 0), "", 900);
        var kpiIssuesBar = el("kpi-issues-bar");
        if (kpiIssuesBar) setTimeout(function() { kpiIssuesBar.style.width = Math.min((data.filtered_count || 0) * 5, 100) + "%"; }, 300);

        var cardsContainer = el("ai-issue-cards-container");
        if (cardsContainer) {
          cardsContainer.innerHTML = "";
          if (data.issues && data.issues.length > 0) {
            data.issues.forEach(function(iss, idx) {
              cardsContainer.appendChild(buildIssueCard(iss, idx));
            });
          } else {
            cardsContainer.innerHTML = '<div class="empty-state" style="padding:16px 0"><span class="empty-icon"><i class="fa-solid fa-circle-check" style="font-size:1.8rem;color:var(--green)"></i></span><p>No AI quality flags at current confidence threshold.</p></div>';
          }
        }
        window.lastAiIssues = data.issues;
        renderClinicalExplainer(data.issues || []);
        if (data.issues && data.issues.length > 0) renderRiskDonutChart(data.issues);
      })
      .catch(function(e) {
        console.error("runAIChecks error:", e);
        showToast("AI scanner failed — is the server running?", "error");
      })
      .finally(function() { setLoading(btn, false, origHtml); });
  }

  function buildIssueCard(iss, idx) {
    var div = document.createElement("div");
    div.className = "issue-card";
    var confPct = Math.round((iss.confidence || 0) * 100);
    div.innerHTML = '<div class="issue-card-header"><div class="issue-card-left"><span class="' + getRiskClass(iss.risk_level) + '">' + getRiskIcon(iss.risk_level) + " " + (iss.risk_level || "Medium") + '</span><span class="issue-card-title">' + iss.type + '</span><span class="issue-card-table">' + iss.table + '</span></div><div class="issue-card-right"><div class="conf-bar"><div class="conf-bar-fill" style="width:' + confPct + '%"></div></div><span class="conf-badge">' + confPct + '%</span></div></div><div class="issue-card-body">' + iss.detail + "</div>";
    return div;
  }

  function getRiskClass(level) {
    var l = (level || "").toLowerCase();
    if (l === "critical") return "risk-badge risk-critical";
    if (l === "high")     return "risk-badge risk-high";
    if (l === "low")      return "risk-badge risk-low";
    return "risk-badge risk-medium";
  }

  function getRiskIcon(level) {
    var l = (level || "").toLowerCase();
    if (l === "critical") return '<i class="fa-solid fa-skull-crossbones"></i>';
    if (l === "high")     return '<i class="fa-solid fa-circle-exclamation"></i>';
    if (l === "low")      return '<i class="fa-solid fa-circle-info"></i>';
    return '<i class="fa-solid fa-triangle-exclamation"></i>';
  }

  function renderClinicalExplainer(issues) {
    var container = el("clinical-explainer-container");
    var countEl = el("explainer-count");
    if (!container || !issues || !issues.length) return;
    if (countEl) countEl.textContent = issues.length + " Issues";
    container.innerHTML = "";
    issues.slice(0, 6).forEach(function(iss, idx) {
      var card = document.createElement("div");
      card.className = "issue-card";
      card.innerHTML = '<div class="issue-card-header"><div class="issue-card-left"><span class="' + getRiskClass(iss.risk_level) + '">' + getRiskIcon(iss.risk_level) + " " + (iss.risk_level || "Medium") + '</span><span class="issue-card-title">' + iss.type + '</span><span class="issue-card-table">' + iss.table + '</span></div><div class="issue-card-right"><span class="conf-badge">' + Math.round((iss.confidence || 0) * 100) + '% conf.</span></div></div><div class="issue-card-body"><div class="impact-grid"><div class="impact-field"><div class="impact-field-label"><i class="fa-solid fa-heart-pulse"></i> Clinical Impact</div><div class="impact-field-value">' + (iss.clinical_impact || "N/A") + '</div></div><div class="impact-field"><div class="impact-field-label"><i class="fa-solid fa-flask"></i> Research Impact</div><div class="impact-field-value">' + (iss.research_impact || "N/A") + '</div></div><div class="impact-field"><div class="impact-field-label"><i class="fa-solid fa-shield-check"></i> Action</div><div class="impact-field-value">' + (iss.recommended_action || "N/A") + '</div></div><div class="impact-field"><div class="impact-field-label"><i class="fa-solid fa-flag"></i> Priority</div><div class="impact-field-value"><span class="' + getRiskClass(iss.risk_level) + '">' + (iss.risk_level || "Medium") + "</span></div></div></div></div>";
      container.appendChild(card);
    });
  }

  function sendFlagsToQueue() {
    var issues = window.lastAiIssues || [];
    if (!issues.length) {
      showToast("No quality flags generated. Run the AI Scanner first.", "warning");
      return;
    }
    var newCount = 0;
    issues.forEach(function(iss) {
      var exists = reviewQueue.filter(function(q) { return q.table === iss.table && q.type === iss.type && q.detail === iss.detail; }).length > 0;
      if (!exists) {
        reviewQueue.push(Object.assign({}, iss, { status: "pending", notes: "", timestamp: new Date().toISOString(), auditTrail: [] }));
        newCount++;
      }
    });
    updateQueueUI();
    showToast("Routed " + newCount + " AI flags to the Human Review Queue.", "success");
    var reviewTab = qs('[data-tab="tab-review"]');
    if (reviewTab) reviewTab.click();
  }

  function updateQueueUI() {
    var badge = el("queue-count-badge");
    if (badge) badge.textContent = reviewQueue.length;
    var pending  = reviewQueue.filter(function(q) { return q.status === "pending"; }).length;
    var accepted = reviewQueue.filter(function(q) { return q.status === "accepted"; }).length;
    var rejected = reviewQueue.filter(function(q) { return q.status === "rejected"; }).length;
    var pEl = el("queue-pending-count");
    var aEl = el("queue-accepted-count");
    var rEl = el("queue-rejected-count");
    if (pEl) animateCountUp(pEl, pending, "", 500);
    if (aEl) animateCountUp(aEl, accepted, "", 500);
    if (rEl) animateCountUp(rEl, rejected, "", 500);
    renderQueueCards();
  }

  function renderQueueCards() {
    var container = el("queue-container");
    if (!container) return;
    container.innerHTML = "";
    if (reviewQueue.length === 0) {
      container.innerHTML = '<div class="empty-state"><span class="empty-icon"><i class="fa-solid fa-folder-open"></i></span><p>No issues in the review queue. Run the AI Scanner and route flags here.</p></div>';
      return;
    }
    var filtered = currentFilter === "all" ? reviewQueue : reviewQueue.filter(function(q) { return q.status === currentFilter; });
    if (filtered.length === 0) {
      container.innerHTML = '<div class="empty-state"><span class="empty-icon"><i class="fa-solid fa-filter-circle-xmark"></i></span><p>No ' + currentFilter + " issues.</p></div>";
      return;
    }
    filtered.forEach(function(item) {
      var realIdx = reviewQueue.indexOf(item);
      var ts = item.timestamp ? new Date(item.timestamp).toLocaleString() : "—";
      var statusPill = item.status === "accepted" ? '<span class="pill pill-green"><i class="fa-solid fa-check"></i> Accepted</span>' : item.status === "rejected" ? '<span class="pill pill-red"><i class="fa-solid fa-xmark"></i> Rejected</span>' : '<span class="pill pill-amber"><i class="fa-solid fa-clock"></i> Pending</span>';
      var trailHtml = (item.auditTrail || []).map(function(t) { return '<div class="audit-entry"><span class="audit-time">' + t.time + "</span><span class='audit-action'>&rarr; " + t.action + "</span></div>"; }).join("");
      var div = document.createElement("div");
      div.className = "queue-card status-" + item.status;
      div.innerHTML = '<div class="queue-card-header"><div><div class="queue-card-meta"><span class="' + getRiskClass(item.risk_level) + '">' + getRiskIcon(item.risk_level) + " " + (item.risk_level || "Medium") + "</span><span class='font-bold text-sm'>" + item.type + "</span><span class='issue-card-table'>" + item.table + "</span>" + statusPill + '</div><div class="queue-card-desc">' + item.detail + "</div>" + (item.recommended_action ? '<div class="queue-card-action"><i class="fa-solid fa-lightbulb"></i> <strong>Action:</strong> ' + item.recommended_action + "</div>" : "") + '</div></div><div class="mt-3"><label class="text-xs text-muted font-bold" style="display:block;margin-bottom:6px"><i class="fa-solid fa-note-sticky"></i> Reviewer Notes</label><textarea class="queue-notes" placeholder="Add review notes here..." data-idx="' + realIdx + '">' + (item.notes || "") + '</textarea></div><div class="queue-card-actions"><button class="btn btn-success btn-sm btn-accept" data-idx="' + realIdx + '"><i class="fa-solid fa-check"></i> Accept</button><button class="btn btn-danger btn-sm btn-reject" data-idx="' + realIdx + '"><i class="fa-solid fa-xmark"></i> Reject</button><button class="btn btn-ghost btn-sm btn-reset" data-idx="' + realIdx + '"><i class="fa-solid fa-rotate-left"></i> Reset</button><span class="queue-timestamp"><i class="fa-regular fa-clock"></i> ' + ts + "</span></div>" + (trailHtml ? '<div class="audit-trail">' + trailHtml + "</div>" : "");
      container.appendChild(div);
    });

    container.querySelectorAll(".queue-notes").forEach(function(textarea) {
      textarea.addEventListener("input", function(e) {
        var idx = parseInt(e.target.getAttribute("data-idx"));
        if (!isNaN(idx)) reviewQueue[idx].notes = e.target.value;
      });
    });
    container.querySelectorAll(".btn-accept").forEach(function(b) {
      b.addEventListener("click", function(e) {
        var idx = parseInt(e.target.closest("button").getAttribute("data-idx"));
        logAuditAction(idx, "ACCEPTED");
        reviewQueue[idx].status = "accepted";
        updateQueueUI();
        showToast("Issue accepted and logged.", "success");
      });
    });
    container.querySelectorAll(".btn-reject").forEach(function(b) {
      b.addEventListener("click", function(e) {
        var idx = parseInt(e.target.closest("button").getAttribute("data-idx"));
        logAuditAction(idx, "REJECTED");
        reviewQueue[idx].status = "rejected";
        updateQueueUI();
        showToast("Issue rejected — marked as false positive.", "info");
      });
    });
    container.querySelectorAll(".btn-reset").forEach(function(b) {
      b.addEventListener("click", function(e) {
        var idx = parseInt(e.target.closest("button").getAttribute("data-idx"));
        logAuditAction(idx, "RESET TO PENDING");
        reviewQueue[idx].status = "pending";
        updateQueueUI();
      });
    });
  }

  function logAuditAction(idx, action) {
    if (!reviewQueue[idx]) return;
    if (!reviewQueue[idx].auditTrail) reviewQueue[idx].auditTrail = [];
    reviewQueue[idx].auditTrail.push({ time: new Date().toLocaleTimeString(), action: action, note: reviewQueue[idx].notes || "" });
  }

  function fetchLabDistribution(selectedId) {
    var url = API_BASE + "/quality/lab_distribution" + (selectedId ? "?item_id=" + selectedId : "");
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var select = el("lab-item-select");
        if (select && data.items && data.items.length > 0 && select.options.length <= 1) {
          select.innerHTML = "";
          data.items.forEach(function(it) {
            var opt = document.createElement("option");
            opt.value = it.itemid;
            opt.textContent = it.label + " (ID: " + it.itemid + ")";
            if (it.itemid === data.selected_itemid) opt.selected = true;
            select.appendChild(opt);
          });
        }
        var medEl = el("lab-median-val");
        if (medEl) medEl.textContent = data.median || 0;
        var madEl = el("lab-mad-val");
        if (madEl) madEl.textContent = data.mad || 0;
        var countEl = el("lab-count-val");
        if (countEl) countEl.textContent = (data.values ? data.values.length : 0);
        renderLabChart(data.values || []);
      })
      .catch(function(e) { console.error("fetchLabDistribution error:", e); });
  }

  function runMetricEvaluation() {
    var btn = el("btn-run-eval");
    var origHtml = btn ? btn.innerHTML : "";
    setLoading(btn, true);
    fetch(API_BASE + "/evaluation/metrics")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var a = data.ai_score;
        var b = data.baseline_score;
        var recallEl = el("eval-recall-val");
        if (recallEl) animateCountUp(recallEl, a.recall * 100, "%", 900);
        var precEl = el("eval-precision-val");
        if (precEl) animateCountUp(precEl, a.precision_proxy * 100, "%", 900);
        var f1El = el("eval-f1-val");
        if (f1El) animateCountUp(f1El, a.f1_proxy * 100, "%", 900);
        var rDelta = el("eval-recall-delta");
        if (rDelta) rDelta.textContent = "vs Baseline: " + (b.recall * 100).toFixed(1) + "%";
        var pDelta = el("eval-precision-delta");
        if (pDelta) pDelta.textContent = "vs Baseline: " + (b.precision_proxy * 100).toFixed(1) + "%";
        var fDelta = el("eval-f1-delta");
        if (fDelta) fDelta.textContent = "vs Baseline: " + (b.f1_proxy * 100).toFixed(1) + "%";

        var tbody = qs("#eval-matrix-table tbody");
        if (tbody) {
          tbody.innerHTML = '<tr><td><strong>Baseline Rules</strong></td><td class="font-mono">' + b.total_flags_raised + '</td><td><span class="pill pill-grey" style="font-size:0.78rem">' + (b.recall * 100).toFixed(1) + '%</span></td><td><span class="pill pill-grey" style="font-size:0.78rem">' + (b.precision_proxy * 100).toFixed(1) + '%</span></td><td><span class="pill pill-grey" style="font-size:0.78rem">' + (b.f1_proxy * 100).toFixed(1) + '%</span></td></tr><tr><td><strong>AI Quality Scanner</strong> <span class="pill pill-cyan" style="font-size:0.65rem;margin-left:4px">AI</span></td><td class="font-mono">' + a.total_flags_raised + '</td><td><span class="pill pill-cyan" style="font-size:0.78rem">' + (a.recall * 100).toFixed(1) + '%</span></td><td><span class="pill pill-cyan" style="font-size:0.78rem">' + (a.precision_proxy * 100).toFixed(1) + '%</span></td><td><span class="pill pill-cyan" style="font-size:0.78rem">' + (a.f1_proxy * 100).toFixed(1) + "%</span></td></tr>";
        }

        var jsonBox = el("eval-seeds-json");
        if (jsonBox) jsonBox.textContent = JSON.stringify(data.seeds, null, 2);

        var seedsTbody = qs("#eval-seeds-table tbody");
        if (seedsTbody && data.seeds && data.seeds.length > 0) {
          seedsTbody.innerHTML = "";
          data.seeds.forEach(function(seed) {
            var tr = document.createElement("tr");
            var refStr = Object.keys(seed).filter(function(k) { return k !== "type" && k !== "table"; }).map(function(k) { return k + ": " + seed[k]; }).join(", ");
            tr.innerHTML = '<td><span class="font-mono text-cyan text-xs">' + (seed.table || "N/A") + '</span></td><td><span class="pill pill-amber" style="font-size:0.72rem"><i class="fa-solid fa-bullseye"></i> ' + (seed.type || "N/A") + '</span></td><td class="font-mono text-xs text-muted">' + (refStr || "—") + "</td>";
            seedsTbody.appendChild(tr);
          });
        }

        showToast("Evaluation complete — benchmarks computed.", "success");
      })
      .catch(function(e) {
        console.error("runMetricEvaluation error:", e);
        showToast("Evaluation failed — check console.", "error");
      })
      .finally(function() { setLoading(btn, false, origHtml); });
  }

  function downloadPDFReport() {
    showToast("Generating PDF audit report...", "info");
    window.open(API_BASE + "/report/pdf", "_blank");
  }

  function populateReportsTab(scores) {
    if (!scores) return;
    var fields = [
      ["rep-bar-overall",   "rep-score-overall",   scores.overall_score],
      ["rep-bar-missing",   "rep-score-missing",   scores.missing_data_score],
      ["rep-bar-duplicate", "rep-score-duplicate", scores.duplicate_score],
      ["rep-bar-temporal",  "rep-score-temporal",  scores.temporal_score],
      ["rep-bar-outlier",   "rep-score-outlier",   scores.outlier_score],
    ];
    fields.forEach(function(f) {
      var bar = el(f[0]), num = el(f[1]), val = f[2] || 0;
      if (bar) setTimeout(function() { bar.style.width = val + "%"; }, 300);
      if (num) animateCountUp(num, Math.round(val), " / 100", 900);
    });
    var kpiSummary = el("reports-kpi-summary");
    if (kpiSummary) {
      var totalPtsEl = el("metric-total-count");
      var totalPts = totalPtsEl ? totalPtsEl.textContent : "—";
      var totalIssues = cachedIssues.baseline.length + cachedIssues.ai.length;
      kpiSummary.innerHTML = '<div class="flex-between mb-3"><span class="text-sm text-muted">Overall Trust Score</span><span class="font-bold text-cyan">' + Math.round(scores.overall_score) + ' / 100</span></div><div class="flex-between mb-3"><span class="text-sm text-muted">Total Patients</span><span class="font-bold">' + totalPts + '</span></div><div class="flex-between mb-3"><span class="text-sm text-muted">Total Issues Detected</span><span class="font-bold">' + totalIssues + '</span></div><div class="flex-between mb-3"><span class="text-sm text-muted">AI Scanner Flags</span><span class="font-bold text-cyan">' + cachedIssues.ai.length + '</span></div><div class="flex-between"><span class="text-sm text-muted">Baseline Rule Flags</span><span class="font-bold text-amber">' + cachedIssues.baseline.length + "</span></div>";
    }
  }

  /* ==================================================================
     CHART RENDERING
  ================================================================== */

  var CHART_DEFAULTS = {
    color: "#94a3b8",
    gridColor: "rgba(255,255,255,0.05)",
    font: { family: "Inter, sans-serif", size: 12 }
  };

  function hasChartJS() { return typeof Chart !== "undefined"; }

  function getChartOpts() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(6, 12, 24, 0.95)",
          borderColor: "rgba(56, 189, 248, 0.3)",
          borderWidth: 1,
          titleColor: "#f0f6ff",
          bodyColor: "#94a3b8",
          padding: 12,
          cornerRadius: 8
        }
      }
    };
  }

  function renderCohortChart(clauses, counts) {
    if (!hasChartJS()) return;
    var canvas = el("cohortChart");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (cohortChart) cohortChart.destroy();
    var gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, "rgba(56, 189, 248, 0.5)");
    gradient.addColorStop(1, "rgba(56, 189, 248, 0.05)");
    cohortChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: clauses,
        datasets: [{ label: "Matched Patients", data: clauses.map(function(c) { return counts[c] || 0; }), backgroundColor: gradient, borderColor: "#38bdf8", borderWidth: 1, borderRadius: 6, borderSkipped: false }]
      },
      options: Object.assign({}, getChartOpts(), { scales: { y: { grid: { color: CHART_DEFAULTS.gridColor }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font } }, x: { grid: { display: false }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font } } } })
    });
  }

  function renderLabChart(values) {
    if (!hasChartJS()) return;
    var canvas = el("labChart");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (labChart) labChart.destroy();
    var gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, "rgba(56, 189, 248, 0.3)");
    gradient.addColorStop(1, "rgba(56, 189, 248, 0.0)");
    labChart = new Chart(ctx, {
      type: "line",
      data: { labels: values.map(function(_, i) { return i + 1; }), datasets: [{ label: "Reading Value", data: values, borderColor: "#38bdf8", backgroundColor: gradient, fill: true, tension: 0.4, pointRadius: values.length < 50 ? 3 : 1, pointHoverRadius: 6, pointBackgroundColor: "#38bdf8", borderWidth: 2 }] },
      options: Object.assign({}, getChartOpts(), { scales: { y: { grid: { color: CHART_DEFAULTS.gridColor }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font } }, x: { grid: { color: CHART_DEFAULTS.gridColor }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font, maxTicksLimit: 12 } } } })
    });
  }

  function renderRiskDonutChart(issues) {
    if (!hasChartJS()) return;
    var canvas = el("riskDonutChart");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (riskDonutChart) riskDonutChart.destroy();
    var counts = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    issues.forEach(function(iss) {
      var level = iss.risk_level || "Medium";
      if (counts.hasOwnProperty(level)) counts[level]++; else counts.Medium++;
    });
    riskDonutChart = new Chart(ctx, {
      type: "doughnut",
      data: { labels: ["Critical", "High", "Medium", "Low"], datasets: [{ data: [counts.Critical, counts.High, counts.Medium, counts.Low], backgroundColor: ["rgba(255,45,85,0.8)", "rgba(255,159,10,0.8)", "rgba(56,189,248,0.8)", "rgba(16,185,129,0.8)"], borderColor: ["rgba(255,45,85,0.2)", "rgba(255,159,10,0.2)", "rgba(56,189,248,0.2)", "rgba(16,185,129,0.2)"], borderWidth: 2, hoverOffset: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "72%", plugins: { legend: { display: true, position: "right", labels: { color: "#94a3b8", padding: 16, font: { family: "Inter, sans-serif", size: 12 }, usePointStyle: true, pointStyleWidth: 8 } }, tooltip: { backgroundColor: "rgba(6,12,24,0.95)", borderColor: "rgba(56,189,248,0.3)", borderWidth: 1, titleColor: "#f0f6ff", bodyColor: "#94a3b8", padding: 12, cornerRadius: 8 } } }
    });
  }

  function renderQualityBreakdownChart(scores) {
    if (!hasChartJS()) return;
    var canvas = el("qualityBreakdownChart");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (qualityBreakdownChart) qualityBreakdownChart.destroy();
    var labels = ["Missing Data", "Duplicates", "Temporal", "Outliers", "Overall"];
    var values = [scores.missing_data_score, scores.duplicate_score, scores.temporal_score, scores.outlier_score, scores.overall_score];
    var colors = values.map(function(v) { return v >= 80 ? "rgba(16,185,129,0.7)" : v >= 60 ? "rgba(56,189,248,0.7)" : v >= 40 ? "rgba(245,158,11,0.7)" : "rgba(239,68,68,0.7)"; });
    qualityBreakdownChart = new Chart(ctx, {
      type: "bar",
      data: { labels: labels, datasets: [{ label: "Score", data: values, backgroundColor: colors, borderColor: colors.map(function(c) { return c.replace("0.7", "1"); }), borderWidth: 1, borderRadius: 6, borderSkipped: false }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { backgroundColor: "rgba(6,12,24,0.95)", borderColor: "rgba(56,189,248,0.3)", borderWidth: 1, titleColor: "#f0f6ff", bodyColor: "#94a3b8", padding: 12, cornerRadius: 8 } }, scales: { x: { min: 0, max: 100, grid: { color: CHART_DEFAULTS.gridColor }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font } }, y: { grid: { display: false }, ticks: { color: CHART_DEFAULTS.color, font: CHART_DEFAULTS.font } } } }
    });
  }

});

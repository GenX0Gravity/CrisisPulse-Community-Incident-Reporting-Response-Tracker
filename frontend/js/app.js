/**
 * CrisisPulse Main Application Controller
 */

class CrisisPulseApp {
  constructor() {
    this.incidents = [];
    this.filteredIncidents = [];
    this.autoRefreshTimer = null;

    this.initElements();
    this.bindEvents();
  }

  initElements() {
    this.apiStatusDot = document.getElementById("api-status-dot");
    this.apiStatusText = document.getElementById("api-status-text");

    // Navigation Tabs
    this.navTabs = document.querySelectorAll(".nav-tab");
    this.tabContents = document.querySelectorAll(".tab-content");

    // Metrics
    this.metricTotal = document.getElementById("metric-total");
    this.metricCritical = document.getElementById("metric-critical");
    this.metricUnderReview = document.getElementById("metric-under-review");
    this.metricInProgress = document.getElementById("metric-in-progress");
    this.metricResolved = document.getElementById("metric-resolved");

    // Feed elements
    this.feedContainer = document.getElementById("incident-feed-container");
    this.searchInput = document.getElementById("feed-search");
    this.categoryFilter = document.getElementById("filter-category");
    this.priorityFilter = document.getElementById("filter-priority");
    this.statusFilter = document.getElementById("filter-status");
    this.btnRefresh = document.getElementById("btn-refresh-feed");

    // Coordinator view elements
    this.coordinatorTableBody = document.getElementById("coordinator-table-body");
  }

  bindEvents() {
    // Tab switching
    this.navTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const targetTab = tab.dataset.tab;
        this.switchTab(targetTab);
      });
    });

    // Feed filtering
    if (this.searchInput) {
      this.searchInput.addEventListener("input", () => this.applyFilters());
    }
    if (this.categoryFilter) {
      this.categoryFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.priorityFilter) {
      this.priorityFilter.addEventListener("change", () => this.applyFilters());
    }
    if (this.statusFilter) {
      this.statusFilter.addEventListener("change", () => this.applyFilters());
    }

    // Refresh button
    if (this.btnRefresh) {
      this.btnRefresh.addEventListener("click", () => this.loadIncidents());
    }
  }

  switchTab(tabName) {
    this.navTabs.forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === tabName);
    });

    this.tabContents.forEach((c) => {
      c.classList.toggle("active", c.id === `tab-${tabName}`);
    });

    if (tabName === "feed" || tabName === "coordinator") {
      this.loadIncidents();
    }
  }

  async init() {
    await this.verifyApiHealth();
    await this.loadIncidents();

    // Initialize sub-controllers
    window.incidentFormController = new window.IncidentFormController();
    window.coordinatorController = new window.CoordinatorController();

    // Start 15s auto-refresh
    this.autoRefreshTimer = setInterval(() => {
      const activeTab = document.querySelector(".nav-tab.active")?.dataset.tab;
      if (activeTab === "feed" || activeTab === "coordinator") {
        this.loadIncidents(true); // silent refresh
      }
    }, 15000);
  }

  async verifyApiHealth() {
    try {
      const health = await window.crisisPulseApi.checkHealth();
      this.apiStatusDot.className = "status-dot online";
      this.apiStatusText.textContent = `API Online (${health.version || "1.0.0"})`;
      if (health.demoMode) {
        this.apiStatusText.textContent += " [Demo Mode]";
      }
    } catch (err) {
      this.apiStatusDot.className = "status-dot offline";
      this.apiStatusText.textContent = `API Disconnected (${window.crisisPulseApi.baseUrl})`;
    }
  }

  async loadIncidents(silent = false) {
    if (!silent && this.feedContainer) {
      this.feedContainer.innerHTML = `
        <div class="state-box">
          <span class="spinner"></span>
          <p style="margin-top: 0.5rem; color: var(--text-muted);">Querying live incident records from DynamoDB...</p>
        </div>
      `;
    }

    try {
      const data = await window.crisisPulseApi.listIncidents({ limit: 50 });
      this.incidents = data.incidents || [];
      this.updateMetrics();
      this.applyFilters();
      this.renderCoordinatorTable();
    } catch (err) {
      if (this.feedContainer) {
        this.feedContainer.innerHTML = `
          <div class="state-box error">
            <div class="state-icon">⚠️</div>
            <h3 style="margin-bottom: 0.35rem;">Unable to Connect to API Gateway</h3>
            <p style="font-size: 0.85rem; color: var(--text-secondary); max-width: 480px; margin: 0 auto;">
              Endpoint: <code>${window.crisisPulseApi.baseUrl}</code><br/>
              ${err.message}. If deploying to AWS, configure <code>frontend/config.js</code> with your SAM output ApiUrl.
            </p>
            <button class="btn-secondary" style="margin: 1rem auto 0;" onclick="window.crisisPulseApp.loadIncidents()">
              🔄 Retry Connection
            </button>
          </div>
        `;
      }
    }
  }

  updateMetrics() {
    const total = this.incidents.length;
    const critical = this.incidents.filter(
      (i) => (i.priority || "").toLowerCase() === "critical"
    ).length;
    const underReview = this.incidents.filter(
      (i) => (i.status || "").toLowerCase() === "under review"
    ).length;
    const inProgress = this.incidents.filter(
      (i) => (i.status || "").toLowerCase() === "in progress"
    ).length;
    const resolved = this.incidents.filter(
      (i) => (i.status || "").toLowerCase() === "resolved"
    ).length;

    if (this.metricTotal) this.metricTotal.textContent = total;
    if (this.metricCritical) this.metricCritical.textContent = critical;
    if (this.metricUnderReview) this.metricUnderReview.textContent = underReview;
    if (this.metricInProgress) this.metricInProgress.textContent = inProgress;
    if (this.metricResolved) this.metricResolved.textContent = resolved;
  }

  applyFilters() {
    const q = (this.searchInput?.value || "").toLowerCase().trim();
    const cat = this.categoryFilter?.value || "all";
    const pri = this.priorityFilter?.value || "all";
    const st = this.statusFilter?.value || "all";

    this.filteredIncidents = this.incidents.filter((inc) => {
      // Text search
      if (q) {
        const textMatch =
          (inc.title || "").toLowerCase().includes(q) ||
          (inc.description || "").toLowerCase().includes(q) ||
          (inc.approximateLocation || "").toLowerCase().includes(q) ||
          (inc.incidentId || "").toLowerCase().includes(q);
        if (!textMatch) return false;
      }

      // Category filter
      if (cat !== "all" && (inc.category || "").toLowerCase() !== cat.toLowerCase()) {
        return false;
      }

      // Priority filter
      if (pri !== "all" && (inc.priority || "").toLowerCase() !== pri.toLowerCase()) {
        return false;
      }

      // Status filter
      if (st !== "all" && (inc.status || "").toLowerCase() !== st.toLowerCase()) {
        return false;
      }

      return true;
    });

    this.renderFeed();
  }

  renderFeed() {
    if (!this.feedContainer) return;

    if (this.filteredIncidents.length === 0) {
      this.feedContainer.innerHTML = `
        <div class="state-box" style="grid-column: 1 / -1;">
          <div class="state-icon">📡</div>
          <h3>No Incidents Found</h3>
          <p class="field-hint">There are no reports matching the active search filters.</p>
        </div>
      `;
      return;
    }

    this.feedContainer.innerHTML = this.filteredIncidents
      .map((inc) => this.renderIncidentCard(inc))
      .join("");
  }

  renderIncidentCard(inc) {
    const pri = (inc.priority || "Medium").toLowerCase();
    const status = inc.status || "Reported";
    const statusClass = status.toLowerCase().replace(/\s+/g, "-");
    const isDup = inc.isPotentialDuplicate;

    let dupBanner = "";
    if (isDup) {
      const nearestCand = (inc.duplicateCandidates && inc.duplicateCandidates[0]) || null;
      const linkBtn = nearestCand
        ? `<button class="duplicate-link-btn" onclick="event.stopPropagation(); window.crisisPulseApp.viewIncidentDetail('${nearestCand.incidentId}')">🔗 View Original Incident (${nearestCand.distanceMeters || 0}m away)</button>`
        : "";
      dupBanner = `
        <div class="duplicate-alert-banner">
          <div>⚠️ ${inc.duplicateReason || "Potential duplicate detected within 300m"}</div>
          ${linkBtn}
        </div>
      `;
    }

    const syntheticTag = inc.isSynthetic
      ? `<span style="font-size: 0.68rem; font-weight: 700; color: #a855f7; background: rgba(168, 85, 247, 0.15); padding: 0.15rem 0.4rem; border-radius: 4px; border: 1px solid rgba(168, 85, 247, 0.3);">DEMO SEED</span>`
      : "";

    const relTime = inc.createdAt
      ? new Date(inc.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";

    return `
      <div class="incident-card" onclick="window.crisisPulseApp.viewIncidentDetail('${inc.incidentId}')">
        <div>
          <div class="incident-card-header">
            <div style="display: flex; gap: 0.35rem; align-items: center; flex-wrap: wrap;">
              <span class="category-tag">${inc.category || "incident"}</span>
              ${syntheticTag}
            </div>
            <div style="display: flex; gap: 0.35rem;">
              <span class="badge-priority ${pri}">${inc.priority || "Unclassified"}</span>
              <span class="badge-status ${statusClass}">${status}</span>
            </div>
          </div>

          <div class="card-location">
            📍 ${inc.approximateLocation || "Location unspecified"}
          </div>

          <p class="card-desc">
            ${inc.description || "No description provided."}
          </p>

          ${dupBanner}
        </div>

        <div class="card-footer">
          <span>🕒 ${relTime}</span>
          <span style="font-family: monospace;">ID: ${inc.incidentId.slice(0, 8)}...</span>
        </div>
      </div>
    `;
  }

  renderCoordinatorTable() {
    if (!this.coordinatorTableBody) return;

    if (this.incidents.length === 0) {
      this.coordinatorTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
            No incidents reported yet.
          </td>
        </tr>
      `;
      return;
    }

    this.coordinatorTableBody.innerHTML = this.incidents
      .map((inc) => {
        const pri = (inc.priority || "medium").toLowerCase();
        const status = inc.status || "Reported";
        const statusClass = status.toLowerCase().replace(/\s+/g, "-");
        return `
          <tr style="border-bottom: 1px solid var(--border-subtle); cursor: pointer;" onclick="window.crisisPulseApp.viewIncidentDetail('${inc.incidentId}')">
            <td style="padding: 0.75rem 1rem; font-family: monospace; font-size: 0.8rem; color: var(--cyan-light);">
              ${inc.incidentId.slice(0, 8)}...
            </td>
            <td style="padding: 0.75rem 1rem; font-weight: 600;">
              ${(inc.category || "other").toUpperCase()}
            </td>
            <td style="padding: 0.75rem 1rem; font-size: 0.85rem;">
              ${inc.approximateLocation || "—"}
            </td>
            <td style="padding: 0.75rem 1rem;">
              <span class="badge-priority ${pri}">${inc.priority || "Unclassified"}</span>
            </td>
            <td style="padding: 0.75rem 1rem;">
              <span class="badge-status ${statusClass}">${status}</span>
            </td>
            <td style="padding: 0.75rem 1rem; text-align: right;">
              <button class="btn-secondary" style="display: inline-flex;" onclick="event.stopPropagation(); window.crisisPulseApp.viewIncidentDetail('${inc.incidentId}')">
                Inspect
              </button>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  viewIncidentDetail(incidentId) {
    if (window.coordinatorController) {
      window.coordinatorController.openInspector(incidentId);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.crisisPulseApp = new CrisisPulseApp();
  window.crisisPulseApp.init();
});

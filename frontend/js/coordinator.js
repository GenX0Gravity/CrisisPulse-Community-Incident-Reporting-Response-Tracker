/**
 * Coordinator Operations Center Controller
 *
 * Provides incident triage, status transitions (POST /coordinator/incidents/{id}/status),
 * inspection of deterministic scoring breakdown, duplicate links, and status history timeline.
 * Never embeds administrator credentials or shared secrets.
 */

class CoordinatorController {
  constructor() {
    this.activeIncident = null;
    this.sessionAuthToken = ""; // In-memory only; never hardcoded or persisted to localStorage
    this.initElements();
    this.bindEvents();
  }

  initElements() {
    this.modal = document.getElementById("incident-modal");
    this.modalTitle = document.getElementById("modal-incident-title");
    this.modalBody = document.getElementById("modal-incident-body");
    this.btnCloseModal = document.getElementById("btn-close-modal");
  }

  bindEvents() {
    if (this.btnCloseModal) {
      this.btnCloseModal.addEventListener("click", () => this.closeModal());
    }

    if (this.modal) {
      this.modal.addEventListener("click", (e) => {
        if (e.target === this.modal) this.closeModal();
      });
    }
  }

  closeModal() {
    if (this.modal) {
      this.modal.classList.remove("active");
    }
    this.activeIncident = null;
  }

  async openInspector(incidentId) {
    if (!this.modal) return;

    this.modal.classList.add("active");
    this.modalTitle.textContent = `Incident ${incidentId.slice(0, 8)}...`;
    this.modalBody.innerHTML = `
      <div style="text-align: center; padding: 2.5rem;">
        <span class="spinner"></span>
        <p style="margin-top: 0.5rem; color: var(--text-muted);">Fetching incident & timeline from DynamoDB...</p>
      </div>
    `;

    try {
      const incident = await window.crisisPulseApi.getIncident(incidentId);
      this.activeIncident = incident;
      this.renderInspectorContent(incident);
    } catch (err) {
      this.modalBody.innerHTML = `
        <div class="state-box error">
          <p>Failed to load incident: ${err.message}</p>
        </div>
      `;
    }
  }

  renderInspectorContent(inc) {
    const isDup = inc.isPotentialDuplicate;
    const priClass = (inc.priority || "medium").toLowerCase();
    const statusClass = (inc.status || "Reported").toLowerCase().replace(/\s+/g, "-");

    // Photo preview via short-lived presigned GET URL
    const photoSection = inc.photoUrl
      ? `
        <div class="form-group" style="margin-top: 1rem;">
          <label>Attached Scene Photo (Presigned Private Access):</label>
          <div style="max-width: 340px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-card); margin-top: 0.35rem;">
            <a href="${inc.photoUrl}" target="_blank" title="Click to view full image in new tab">
              <img src="${inc.photoUrl}" alt="Incident Photo" style="width: 100%; height: auto; display: block;" />
            </a>
          </div>
          <p class="field-hint">${inc.photoValidationReason || "Private S3 object accessible via short-lived presigned URL."}</p>
        </div>
      `
      : "";

    // Duplicate candidates & clickable links
    let dupDetails = "";
    if (isDup) {
      let candidateLinks = "";
      if (inc.duplicateCandidates && inc.duplicateCandidates.length > 0) {
        candidateLinks = inc.duplicateCandidates
          .map(
            (c) => `
            <button class="duplicate-link-btn" onclick="window.coordinatorController.openInspector('${c.incidentId}')">
              🔗 View Matching Incident (${c.incidentId.slice(0, 8)}... — ${c.distanceMeters || 0}m away)
            </button>
          `
          )
          .join(" ");
      }

      dupDetails = `
        <div class="duplicate-alert-banner" style="margin: 0.75rem 0;">
          <div>
            <strong>⚠️ Potential Duplicate Detected</strong>
            <p style="margin-top: 0.2rem;">${inc.duplicateReason || "Report within 300m and 24h window matches this category."}</p>
            ${candidateLinks ? `<div style="margin-top: 0.4rem;">${candidateLinks}</div>` : ""}
          </div>
        </div>
      `;
    }

    // Status History Timeline
    const historyEntries = inc.statusHistory || [
      {
        status: inc.status || "Reported",
        timestamp: inc.createdAt || new Date().toISOString(),
        actor: "system",
        notes: "Initial report received.",
      },
    ];

    const timelineHtml = `
      <div class="form-group" style="margin-top: 1.25rem;">
        <label>Status History Timeline (Audit Trail):</label>
        <div class="timeline-wrap">
          ${historyEntries
            .map((entry, idx) => {
              const isCurrent = idx === historyEntries.length - 1;
              const dateStr = entry.timestamp
                ? new Date(entry.timestamp).toLocaleString()
                : "—";
              return `
                <div class="timeline-item">
                  <span class="timeline-dot ${isCurrent ? "current" : ""}"></span>
                  <div class="timeline-header">
                    <span class="badge-status ${entry.status.toLowerCase().replace(/\s+/g, "-")}">${entry.status}</span>
                    <span style="font-weight: 500; color: var(--text-muted); font-size: 0.75rem;">by ${entry.actor || "system"}</span>
                  </div>
                  <div class="timeline-meta">${dateStr}</div>
                  ${entry.notes ? `<div class="timeline-notes">${entry.notes}</div>` : ""}
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;

    // Allowed status transitions buttons based on canonical status
    const currentStatus = inc.status || "Reported";
    let transitionButtons = "";

    if (currentStatus === "Reported") {
      transitionButtons = `
        <button class="btn-secondary" style="border-color: var(--status-review-border); color: var(--status-review);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'Under Review')">
          📋 Transition to Under Review
        </button>
      `;
    } else if (currentStatus === "Under Review") {
      transitionButtons = `
        <button class="btn-secondary" style="border-color: var(--status-progress-border); color: var(--cyan-light);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'In Progress')">
          ⚡ Dispatch / Mark In Progress
        </button>
        <button class="btn-secondary" style="border-color: var(--status-resolved-border); color: var(--priority-low);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'Resolved')">
          ✓ Mark Resolved
        </button>
      `;
    } else if (currentStatus === "In Progress") {
      transitionButtons = `
        <button class="btn-secondary" style="border-color: var(--status-resolved-border); color: var(--priority-low);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'Resolved')">
          ✓ Mark Resolved
        </button>
        <button class="btn-secondary" style="border-color: var(--status-review-border); color: var(--status-review);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'Under Review')">
          ↩ Return to Under Review
        </button>
      `;
    } else if (currentStatus === "Resolved") {
      transitionButtons = `
        <button class="btn-secondary" style="border-color: var(--status-progress-border); color: var(--cyan-light);" onclick="window.coordinatorController.changeStatus('${inc.incidentId}', 'In Progress')">
          🔄 Re-Open Incident (In Progress)
        </button>
      `;
    }

    const riskBadges = (inc.riskFactors && inc.riskFactors.length > 0)
      ? inc.riskFactors.map(rf => `<span class="category-tag" style="font-size: 0.72rem;">${rf.replace(/_/g, ' ')}</span>`).join(" ")
      : "<span style='color: var(--text-muted); font-size: 0.8rem;'>None reported</span>";

    this.modalTitle.textContent = `${(inc.category || "incident").toUpperCase()} — ${inc.approximateLocation || "Unknown Location"}`;

    this.modalBody.innerHTML = `
      <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
        <span class="badge-priority ${priClass}">${inc.priority || "Unclassified"} (${inc.priorityScore || 0}/100)</span>
        <span class="badge-status ${statusClass}">${inc.status}</span>
        <span class="category-tag">${inc.category}</span>
      </div>

      ${dupDetails}

      <div class="form-group">
        <label>Factual Incident Description:</label>
        <p style="color: var(--text-primary); font-size: 0.9rem; background: var(--bg-input); padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border-subtle);">
          ${inc.description}
        </p>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 0.75rem;">
        <div>
          <label style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Location:</label>
          <p style="font-size: 0.88rem; font-weight: 600;">📍 ${inc.approximateLocation}</p>
          ${inc.latitude ? `<p style="font-size: 0.75rem; color: var(--text-muted);">Lat: ${inc.latitude}, Lon: ${inc.longitude}</p>` : ""}
        </div>
        <div>
          <label style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Reporter & Time:</label>
          <p style="font-size: 0.88rem;">${inc.reporterName || "Anonymous"}</p>
          <p style="font-size: 0.75rem; color: var(--text-muted);">${inc.createdAt ? new Date(inc.createdAt).toLocaleString() : ""}</p>
        </div>
      </div>

      <div class="form-group">
        <label>Reported Risk Factors:</label>
        <div style="margin-top: 0.35rem;">${riskBadges}</div>
      </div>

      <!-- Deterministic Rule-Based Scoring Explanation -->
      <div class="form-group" style="background: var(--bg-input); border-radius: 8px; padding: 0.85rem; border: 1px solid var(--border-subtle);">
        <label style="color: var(--cyan-light); font-size: 0.8rem;">Deterministic Scoring Explanation (Rule-Based, Zero AI Claims):</label>
        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.25rem;">
          ${inc.priorityExplanation || "Calculated deterministically from category baseline and explicit risk factors."}
        </p>
      </div>

      ${photoSection}
      ${timelineHtml}

      <hr style="border: 0; border-top: 1px solid var(--border-subtle); margin: 1.25rem 0;" />

      <!-- Protected Coordinator Status Operations -->
      <div class="coord-auth-banner">
        <strong>🔒 Coordinator Status Management</strong>
        <p style="margin-top: 0.25rem; font-size: 0.78rem;">
          Public users have read-only permissions on incident lifecycle status. Status updates require coordinator authorization via <code>POST /coordinator/incidents/{id}/status</code>.
          For the weekend demonstration, if Cognito is not enabled, public status modifications are rejected and transitions can be performed directly through authenticated AWS Console operations.
        </p>

        <div style="margin-top: 0.6rem; display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
          <input type="password" id="coord-session-token" class="form-control" placeholder="Optional Cognito Bearer token (in-memory)" style="max-width: 280px; padding: 0.4rem 0.6rem; font-size: 0.78rem;" value="${this.sessionAuthToken}" onchange="window.coordinatorController.setSessionToken(this.value)" />
          <span style="font-size: 0.72rem; color: var(--text-muted);">(Never saved in storage or code)</span>
        </div>
      </div>

      <div class="form-group">
        <label>Execute Allowed State Transition:</label>
        <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap;">
          ${transitionButtons || "<span style='color: var(--text-muted); font-size: 0.85rem;'>No further transitions available.</span>"}
        </div>
      </div>
    `;
  }

  setSessionToken(token) {
    this.sessionAuthToken = token.trim();
  }

  async changeStatus(incidentId, newStatus) {
    const notes = prompt(`Enter optional coordinator transition notes for transitioning to "${newStatus}":`, `Status moved to ${newStatus} by coordinator.`);
    if (notes === null) return; // User cancelled prompt

    try {
      const response = await window.crisisPulseApi.coordinatorUpdateStatus(
        incidentId,
        newStatus,
        notes,
        this.sessionAuthToken
      );

      alert(`Status successfully transitioned to "${newStatus}"!`);
      this.openInspector(incidentId);

      // Refresh live feed
      if (window.crisisPulseApp) {
        window.crisisPulseApp.loadIncidents();
      }
    } catch (err) {
      alert(`Status Transition Denied: ${err.message}\n\nNote: Public users cannot modify status. In a demo environment without Cognito credentials, demonstrate transitions via authenticated AWS Console DynamoDB operations.`);
    }
  }
}

window.CoordinatorController = CoordinatorController;

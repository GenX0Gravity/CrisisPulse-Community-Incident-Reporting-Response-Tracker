/**
 * Incident Submission Form Controller
 *
 * Handles client-side validation, presigned S3 photo uploads,
 * idempotency key management, and asynchronous Step Functions polling.
 */

class IncidentFormController {
  constructor() {
    this.selectedCategory = "fire";
    this.selectedFile = null;
    this.currentIdempotencyKey = this.generateUuid();
    this.pollInterval = null;

    this.initElements();
    this.bindEvents();
  }

  generateUuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  initElements() {
    this.form = document.getElementById("incident-form");
    this.categoryOptions = document.querySelectorAll(".category-option");
    this.descInput = document.getElementById("field-description");
    this.descCounter = document.getElementById("desc-counter");
    this.locationInput = document.getElementById("field-location");
    this.latInput = document.getElementById("field-latitude");
    this.lonInput = document.getElementById("field-longitude");
    this.btnGps = document.getElementById("btn-use-gps");
    this.fileInput = document.getElementById("field-photo");
    this.dropzone = document.getElementById("photo-dropzone");
    this.previewWrap = document.getElementById("photo-preview-wrap");
    this.previewImg = document.getElementById("photo-preview-img");
    this.btnRemovePhoto = document.getElementById("btn-remove-photo");
    this.submitBtn = document.getElementById("btn-submit-incident");
    this.pollCard = document.getElementById("workflow-poll-card");
    this.pollStatus = document.getElementById("poll-status-text");
    this.pollDetails = document.getElementById("poll-result-details");
    this.formAlert = document.getElementById("form-alert-banner");
  }

  bindEvents() {
    // Category selection
    this.categoryOptions.forEach((btn) => {
      btn.addEventListener("click", () => {
        this.categoryOptions.forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        this.selectedCategory = btn.dataset.category;
      });
    });

    // Description counter
    if (this.descInput) {
      this.descInput.addEventListener("input", () => {
        const len = this.descInput.value.length;
        if (this.descCounter) this.descCounter.textContent = `${len}/2000`;
      });
    }

    // GPS location
    if (this.btnGps) {
      this.btnGps.addEventListener("click", () => this.acquireGpsLocation());
    }

    // Photo drag & drop
    if (this.dropzone && this.fileInput) {
      this.dropzone.addEventListener("click", () => this.fileInput.click());
      this.fileInput.addEventListener("change", (e) =>
        this.handleFileSelected(e.target.files[0])
      );

      ["dragenter", "dragover"].forEach((event) => {
        this.dropzone.addEventListener(event, (e) => {
          e.preventDefault();
          this.dropzone.classList.add("dragover");
        });
      });

      ["dragleave", "drop"].forEach((event) => {
        this.dropzone.addEventListener(event, (e) => {
          e.preventDefault();
          this.dropzone.classList.remove("dragover");
        });
      });

      this.dropzone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          this.handleFileSelected(e.dataTransfer.files[0]);
        }
      });
    }

    // Remove photo
    if (this.btnRemovePhoto) {
      this.btnRemovePhoto.addEventListener("click", (e) => {
        e.stopPropagation();
        this.clearPhotoSelection();
      });
    }

    // Form submission
    if (this.form) {
      this.form.addEventListener("submit", (e) => this.handleSubmit(e));
    }
  }

  acquireGpsLocation() {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    this.btnGps.disabled = true;
    this.btnGps.innerHTML = `<span class="spinner"></span> Locating...`;

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(6));
        const lon = parseFloat(pos.coords.longitude.toFixed(6));
        this.latInput.value = lat;
        this.lonInput.value = lon;
        this.btnGps.disabled = false;
        this.btnGps.innerHTML = `✓ Located`;
        setTimeout(() => {
          this.btnGps.innerHTML = `📍 GPS`;
        }, 3000);
      },
      (err) => {
        this.btnGps.disabled = false;
        this.btnGps.innerHTML = `📍 GPS`;
        alert(`Could not acquire location: ${err.message}`);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  }

  handleFileSelected(file) {
    if (!file) return;

    // Check size <= 5MB
    const maxMb = window.CRISIS_PULSE_CONFIG?.MAX_IMAGE_SIZE_MB || 5;
    if (file.size > maxMb * 1024 * 1024) {
      alert(`Photo exceeds the maximum allowed size of ${maxMb}MB.`);
      this.clearPhotoSelection();
      return;
    }

    // Check type
    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) {
      alert("Please upload a valid JPEG, PNG, or WebP image.");
      this.clearPhotoSelection();
      return;
    }

    this.selectedFile = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
      this.previewImg.src = e.target.result;
      this.previewWrap.style.display = "block";
      this.dropzone.querySelector(".dropzone-content").style.display = "none";
    };
    reader.readAsDataURL(file);
  }

  clearPhotoSelection() {
    this.selectedFile = null;
    if (this.fileInput) this.fileInput.value = "";
    if (this.previewWrap) this.previewWrap.style.display = "none";
    if (this.dropzone) {
      this.dropzone.querySelector(".dropzone-content").style.display = "flex";
    }
  }

  showError(message) {
    if (this.formAlert) {
      this.formAlert.textContent = message;
      this.formAlert.style.display = "block";
      this.formAlert.className = "state-box error";
    } else {
      alert(message);
    }
  }

  clearError() {
    if (this.formAlert) {
      this.formAlert.style.display = "none";
      this.formAlert.textContent = "";
    }
  }

  async handleSubmit(e) {
    e.preventDefault();
    this.clearError();

    const desc = this.descInput.value.trim();
    const loc = this.locationInput.value.trim();
    const latVal = this.latInput.value.trim();
    const lonVal = this.lonInput.value.trim();
    const reporter = document.getElementById("field-reporter")?.value.trim() || "Anonymous";

    // Validation
    if (desc.length < 5) {
      this.showError("Description must be at least 5 characters long.");
      return;
    }

    if (loc.length < 2) {
      this.showError("Approximate location is required.");
      return;
    }

    if ((latVal && !lonVal) || (!latVal && lonVal)) {
      this.showError("Both latitude and longitude must be provided together.");
      return;
    }

    // Gather selected risk factors
    const riskCheckboxes = document.querySelectorAll("input[name='riskFactors']:checked");
    const riskFactors = Array.from(riskCheckboxes).map((cb) => cb.value);

    // Prepare UI for submission
    this.submitBtn.disabled = true;
    this.submitBtn.innerHTML = `<span class="spinner"></span> Processing...`;

    try {
      let photoKey = "";

      // 1. Upload photo if selected
      if (this.selectedFile) {
        this.submitBtn.innerHTML = `<span class="spinner"></span> Uploading photo to private S3...`;
        const uploadDetails = await window.crisisPulseApi.requestUploadUrl(
          this.selectedFile.name,
          this.selectedFile.type
        );

        await window.crisisPulseApi.uploadFileToS3(
          uploadDetails.uploadUrl,
          this.selectedFile
        );

        photoKey = uploadDetails.photoKey;
      }

      // 2. Submit incident report
      this.submitBtn.innerHTML = `<span class="spinner"></span> Saving report...`;

      const payload = {
        category: this.selectedCategory,
        description: desc,
        approximateLocation: loc,
        riskFactors,
        photoKey,
        reporterName: reporter,
        idempotencyKey: this.currentIdempotencyKey,
      };

      if (latVal && lonVal) {
        payload.latitude = parseFloat(latVal);
        payload.longitude = parseFloat(lonVal);
      }

      const response = await window.crisisPulseApi.createIncident(
        payload,
        this.currentIdempotencyKey
      );

      const incidentId = response.incidentId || response.incident?.incidentId;

      // 3. Launch live poller for Step Functions completion
      this.startWorkflowPolling(incidentId);

      // Reset form fields
      this.form.reset();
      this.clearPhotoSelection();
      this.currentIdempotencyKey = this.generateUuid();
    } catch (err) {
      this.showError(`Submission error: ${err.message}`);
    } finally {
      this.submitBtn.disabled = false;
      this.submitBtn.innerHTML = `🚨 Submit Incident Report`;
    }
  }

  startWorkflowPolling(incidentId) {
    if (this.pollInterval) clearInterval(this.pollInterval);

    this.pollCard.style.display = "block";
    this.pollStatus.innerHTML = `Incident <code>${incidentId}</code> saved. Step Functions workflow active...`;
    this.pollDetails.innerHTML = `<p class="field-hint">Executing deterministic priority scoring and bounded duplicate verification...</p>`;

    let attempts = 0;
    const maxAttempts = window.CRISIS_PULSE_CONFIG?.MAX_POLL_ATTEMPTS || 25;
    const interval = window.CRISIS_PULSE_CONFIG?.POLL_INTERVAL_MS || 2000;

    this.pollInterval = setInterval(async () => {
      attempts++;
      try {
        const incident = await window.crisisPulseApi.getIncident(incidentId);

        // Check if workflow completed (transitioned from initial submission or completed triage)
        const isEnriched =
          incident &&
          (incident.status !== "Reported" ||
            incident.workflowMetadata?.state === "COMPLETED" ||
            Boolean(incident.priorityExplanation));

        if (isEnriched) {
          clearInterval(this.pollInterval);
          this.pollProgressComplete(incident);
        } else if (attempts >= maxAttempts) {
          clearInterval(this.pollInterval);
          this.pollStatus.innerHTML = `⚠️ Incident <code>${incidentId}</code> is still processing in background.`;
        }
      } catch (err) {
        // Continue polling until max attempts
        if (attempts >= maxAttempts) {
          clearInterval(this.pollInterval);
          this.pollStatus.textContent = `Polling timed out. Check live feed for updates.`;
        }
      }
    }, interval);
  }

  pollProgressComplete(incident) {
    const isDup = incident.isPotentialDuplicate;
    const dupBadge = isDup
      ? `<div class="duplicate-alert-banner">⚠️ ${incident.duplicateReason || "Potential duplicate detected"}</div>`
      : "";

    const statusClass = (incident.status || "Under Review").toLowerCase().replace(/\s+/g, "-");
    this.pollStatus.innerHTML = `✅ Processing Complete — Status: <span class="badge-status ${statusClass}">${incident.status}</span>`;
    this.pollDetails.innerHTML = `
      <div style="margin-top: 0.5rem;">
        <span class="badge-priority ${incident.priority.toLowerCase()}">${incident.priority} Priority (${incident.priorityScore || 0}/100)</span>
        <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.4rem;">
          ${incident.priorityExplanation || ""}
        </p>
        ${dupBadge}
        <button type="button" class="btn-secondary" style="margin-top: 0.75rem;" onclick="window.crisisPulseApp.viewIncidentDetail('${incident.incidentId}')">
          🔍 Inspect Incident
        </button>
      </div>
    `;

    // Refresh feed in background
    if (window.crisisPulseApp) {
      window.crisisPulseApp.loadIncidents();
    }
  }
}

window.IncidentFormController = IncidentFormController;

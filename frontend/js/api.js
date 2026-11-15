/**
 * CrisisPulse API Client
 *
 * Connects directly to the API Gateway HTTP API or local development server.
 * Never fabricates or fakes responses when the API is unreachable.
 */

class CrisisPulseApi {
  constructor() {
    this.config = window.CRISIS_PULSE_CONFIG || {
      API_BASE_URL: "http://localhost:3000",
    };
  }

  get baseUrl() {
    const configured = (this.config.API_BASE_URL || "").trim();
    // If configured with an AWS API Gateway URL or explicit remote endpoint, use it directly
    if (configured && !configured.includes("localhost") && !configured.includes("127.0.0.1")) {
      return configured.replace(/\/+$/, "");
    }
    // When running locally in browser (e.g. http://localhost:8000 or http://127.0.0.1:8000),
    // automatically match the current host and port to avoid port mismatch issues
    if (typeof window !== "undefined" && window.location && window.location.origin) {
      const origin = window.location.origin;
      if (origin.startsWith("http://localhost") || origin.startsWith("http://127.0.0.1")) {
        return origin.replace(/\/+$/, "");
      }
    }
    return (configured || "http://127.0.0.1:8000").replace(/\/+$/, "");
  }

  /**
   * Safe JSON response parser with informative error reporting for HTML responses
   */
  async _parseJsonResponse(res) {
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch (err) {
      if (text.trim().startsWith("<") || text.includes("<!DOCTYPE") || text.includes("<html")) {
        throw new Error(
          `Received HTML instead of JSON API response from ${res.url || this.baseUrl}. ` +
          `If running locally, please start 'python start_frontend.py' (which serves both the UI and API endpoints) ` +
          `rather than a plain static web server. If deployed to AWS, configure frontend/config.js with your SAM ApiUrl.`
        );
      }
      throw new Error(`Invalid JSON received (${res.status}): ${text.slice(0, 120)}`);
    }
  }

  /**
   * Check service health and demo mode flag
   */
  async checkHealth() {
    const url = `${this.baseUrl}/health`;
    const res = await fetch(url, { method: "GET" });
    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Health check failed with status ${res.status}`);
    }
    return data;
  }

  /**
   * Request a short-lived presigned S3 upload PUT URL
   */
  async requestUploadUrl(filename, contentType) {
    const url = `${this.baseUrl}/uploads`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, contentType }),
    });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Upload URL request failed (${res.status})`);
    }
    return data;
  }

  /**
   * Direct binary upload to S3 via presigned PUT URL
   */
  async uploadFileToS3(uploadUrl, file) {
    // If running in local mock mode
    if (uploadUrl.includes("mock-presigned") || uploadUrl.includes("localhost")) {
      return true;
    }

    const res = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": file.type,
      },
      body: file,
    });

    if (!res.ok) {
      throw new Error(`Direct S3 upload failed with status ${res.status}`);
    }
    return true;
  }

  /**
   * Submit new incident report (Public endpoint)
   */
  async createIncident(payload, idempotencyKey = null) {
    const url = `${this.baseUrl}/incidents`;
    const headers = { "Content-Type": "application/json" };
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Incident submission failed (${res.status})`);
    }
    return data;
  }

  /**
   * List incidents with pagination and sorting
   */
  async listIncidents({ limit = 50, order = "desc", cursor = null } = {}) {
    const query = new URLSearchParams();
    if (limit) query.set("limit", limit.toString());
    if (order) query.set("order", order);
    if (cursor) query.set("cursor", cursor);

    const url = `${this.baseUrl}/incidents?${query.toString()}`;
    const res = await fetch(url, { method: "GET" });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Failed to fetch incidents (${res.status})`);
    }
    return data;
  }

  /**
   * Retrieve single incident by ID (includes presigned GET photo URL)
   */
  async getIncident(incidentId) {
    const url = `${this.baseUrl}/incidents/${encodeURIComponent(incidentId)}`;
    const res = await fetch(url, { method: "GET" });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Incident lookup failed (${res.status})`);
    }
    return data.incident;
  }

  /**
   * Public partial update of an incident record (descriptive fields only)
   */
  async updateIncident(incidentId, fields) {
    const url = `${this.baseUrl}/incidents/${encodeURIComponent(incidentId)}`;
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Incident update failed (${res.status})`);
    }
    return data.incident;
  }

  /**
   * Coordinator status transition endpoint (Requires Authorization)
   * Enforces allowed lifecycle transitions ('Reported' -> 'Under Review' -> 'In Progress' -> 'Resolved')
   */
  async coordinatorUpdateStatus(incidentId, status, notes = "", authToken = null) {
    const url = `${this.baseUrl}/coordinator/incidents/${encodeURIComponent(incidentId)}/status`;
    const headers = { "Content-Type": "application/json" };
    if (authToken) {
      headers["Authorization"] = `Bearer ${authToken.trim()}`;
    }

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ status, notes }),
    });

    const data = await this._parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.error || `Coordinator status update failed (${res.status})`);
    }
    return data;
  }
}

window.crisisPulseApi = new CrisisPulseApi();

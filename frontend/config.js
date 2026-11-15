/**
 * CrisisPulse Frontend Configuration
 *
 * For AWS deployment:
 * Set `API_BASE_URL` to your CloudFormation output `ApiUrl`:
 * e.g., "https://abc123xyz.execute-api.us-east-1.amazonaws.com"
 *
 * For local development:
 * Leave as "" or "http://127.0.0.1:8000" to connect to `python start_frontend.py`.
 */
window.CRISIS_PULSE_CONFIG = {
  // Base URL of the deployed live AWS API Gateway HTTP API
  API_BASE_URL: "https://7pfsdt8cei.execute-api.ap-southeast-2.amazonaws.com/prod",

  // Milliseconds between polling checks for Step Functions completion
  POLL_INTERVAL_MS: 2000,

  // Maximum number of polling attempts before timing out
  MAX_POLL_ATTEMPTS: 25,

  // Maximum allowed image size in megabytes (must align with SAM parameter)
  MAX_IMAGE_SIZE_MB: 5,

  // Default coordinate center (fallback for mock location)
  DEFAULT_MAP_CENTER: {
    latitude: 40.7128,
    longitude: -74.006,
  },
};

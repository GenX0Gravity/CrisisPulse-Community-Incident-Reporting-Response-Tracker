# 🚨 CrisisPulse — Community Incident Reporting & Response Tracker

> **AWS Serverless MVP** built with API Gateway HTTP API, Lambda (Python 3.12),
> DynamoDB (on-demand), S3 (private photos), Step Functions (Standard),
> and CloudFront HTTPS static website hosting.

---

## 📌 Live Deployed Application

- **Live Secure Web Dashboard (HTTPS):** [https://7pfsdt8cei.execute-api.ap-southeast-2.amazonaws.com/prod/](https://7pfsdt8cei.execute-api.ap-southeast-2.amazonaws.com/prod/)
- **API Gateway HTTP API Endpoint:** `https://7pfsdt8cei.execute-api.ap-southeast-2.amazonaws.com/prod`
- **AWS Region:** `ap-southeast-2` (Sydney)
- **Deployment Stack Name:** `CrisisPulse-Prod`
- **GitHub Repository:** [https://github.com/GenX0Gravity/CrisisPulse-Community-Incident-Reporting-Response-Tracker](https://github.com/GenX0Gravity/CrisisPulse-Community-Incident-Reporting-Response-Tracker)

---

## 🏛️ System Architecture

Full architectural diagrams, sequence flows, and threat models are documented in [architecture.md](file:///c:/MyProjects/CrisisPulse-Community-Incident-Reporting-Response-Tracker/architecture.md).

```
 Client (SPA over HTTPS)
     │
     ▼
 Amazon CloudFront (TLS 1.2+ HTTPS) ──▶ Private S3 Website Bucket (OAC)
     │
     ▼
 API Gateway HTTP API  (CORS + Default Route Throttling: 50 req/s, Burst 100)
     │
     ├── GET  /health           → HealthFunction [PUBLIC]
     ├── POST /uploads          → CreateUploadFunction  → S3 Photo Bucket (Presigned PUT, ≤5MB) [PUBLIC]
     ├── POST /incidents        → CreateIncidentFunction → DynamoDB (Idempotency) + SFN [PUBLIC]
     ├── GET  /incidents        → ListIncidentsFunction  → DynamoDB (createdAt-index GSI) [PUBLIC]
     ├── GET  /incidents/{id}   → GetIncidentFunction    → DynamoDB + S3 (Presigned GET) [PUBLIC]
     ├── PATCH /incidents/{id}  → UpdateIncidentFunction → DynamoDB [PROTECTED: CognitoAuthorizer]
     └── POST /coordinator/...  → CoordinatorUpdateStatusFunction → DynamoDB [PROTECTED: CognitoAuthorizer]
                                        │
                                        ▼ (Async StartExecution)
                                Step Functions (Standard)
                                  1. ClassifyAndEnrich (Task Lambda)
                                     ├─ Deterministic Priority Scoring (Rule-based, 0-100)
                                     ├─ Bounded Duplicate Detection (GSI query ≤ 300m, 24h)
                                     └─ S3 Photo Size & Existence Verification
                                  2. PersistIncidentEnrichment (Native DynamoDB updateItem)
                                  3. WorkflowFailed (Catch block -> DynamoDB updateItem)
```

---

## 📂 Repository Layout

```
.
├── template.yaml                          # AWS SAM infrastructure-as-code (Backend + CloudFront Frontend)
├── architecture.md                        # Complete system architecture & threat model
├── README.md                              # Operations manual, deployment guide & API reference
├── .gitignore                             # Ignore build & local files
├── requirements-dev.txt                   # Local test dependencies
├── state_machines/
│   └── incident_workflow.asl.json         # Step Functions ASL definition
├── frontend/                              # Responsive Emergency Dashboard (HTML/CSS/JS)
│   ├── index.html                         # SPA interface & accessible layout
│   ├── config.js                          # API base URL & polling settings
│   ├── css/
│   │   └── styles.css                     # Dark navy & cyan operations styling
│   └── js/
│       ├── api.js                         # Direct API Gateway HTTP client
│       ├── form.js                        # Form submission & live workflow poller
│       ├── coordinator.js                 # Coordinator inspection & PATCH actions
│       └── app.js                         # Feed rendering, filters & metrics
├── scripts/
│   └── seed_demo_data.py                  # Developer-only synthetic demo data generator
├── src/
│   ├── requirements.txt                   # Lambda production dependencies
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── config.py                      # Centralized configuration & thresholds
│   │   ├── scoring.py                     # Deterministic priority scoring engine (0-100)
│   │   ├── duplicate_detection.py         # Haversine distance & GSI bounded query
│   │   ├── lifecycle.py                   # Canonical status lifecycle transitions & timeline
│   │   ├── idempotency.py                 # Idempotency extraction & store
│   │   ├── response.py                    # CORS & Decimal JSON responses
│   │   └── validators.py                  # Strict input validation schemas
│   └── handlers/
│       ├── __init__.py
│       ├── health.py                      # GET  /health (Liveness check)
│       ├── create_upload.py               # POST /uploads (Presigned PUT URL)
│       ├── create_incident.py             # POST /incidents (Save & start workflow)
│       ├── list_incidents.py              # GET  /incidents (GSI query pagination)
│       ├── get_incident.py                # GET  /incidents/{id} (Fetch + presigned GET)
│       ├── update_incident.py             # PATCH /incidents/{id} (Descriptive updates only)
│       ├── coordinator_update_status.py   # POST /coordinator/incidents/{id}/status (Auth protected)
│       └── process_incident.py            # Step Functions task Lambda
├── tests/
│   ├── __init__.py
│   ├── validate_sam.py                    # SAM template & resource linkage validation
│   └── unit/
│       ├── __init__.py
│       ├── test_health.py                 # Health endpoint tests
│       ├── test_scoring.py                # Deterministic priority scoring tests
│       ├── test_duplicate_detection.py    # Haversine & duplicate detection tests
│       ├── test_validators.py             # Validator schema tests
│       ├── test_idempotency.py            # Idempotency handler tests
│       ├── test_workflow.py               # Step Functions processing task tests
│       ├── test_lifecycle.py              # Lifecycle state transitions tests
│       └── test_coordinator_auth.py       # Unauthorized request rejection tests
└── events/
    ├── get_health.json                    # API Gateway mock event for GET /health
    └── create_incident.json               # API Gateway mock event for POST /incidents
```

---

## 🚀 Step-by-Step AWS Deployment Runbook

### Prerequisites
1. **AWS CLI v2**: Install from [aws.amazon.com/cli](https://aws.amazon.com/cli/) and run `aws configure`.
2. **AWS SAM CLI**: Install from [docs.aws.amazon.com/serverless-application-model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).
3. **Python 3.12**: Installed and available on PATH.

### Step 1: Validate & Build Infrastructure
```bash
# Validate CloudFormation & SAM syntax
python tests/validate_sam.py

# Build SAM packages
sam build
```

### Step 2: Deploy to AWS (Guided First Run)
```bash
sam deploy --guided
```
Prompts and recommended inputs:
- **Stack Name**: `CrisisPulse-Prod`
- **AWS Region**: `us-east-1` (or your preferred region)
- **Parameter FrontendOrigin**: `http://localhost:3000` (or your custom domain)
- **Parameter DemoMode**: `true` (set `false` for real S3 image verification)
- **Parameter MaxImageSizeMB**: `5`
- **Parameter PresignedUrlExpirySec**: `300`
- **Parameter CognitoUserPoolArn**: Leave blank for demo mode, or enter Cognito User Pool ARN for production coordinator auth.
- **Confirm changes before deploy**: `Y`
- **Allow SAM CLI IAM role creation**: `Y`

### Step 3: Capture CloudFormation Outputs
When the deployment completes, the terminal will print:
```
Outputs:
-------------------------------------------------------------------------------------------------
Key                 Value
-------------------------------------------------------------------------------------------------
ApiUrl              https://<api-id>.execute-api.us-east-1.amazonaws.com/prod
PhotoBucketName     crisis-pulse-prod-photobucket-xxxx
IncidentsTableName  crisis-pulse-prod-incidentstable-xxxx
IncidentWorkflowArn arn:aws:states:us-east-1:xxxx:stateMachine:IncidentWorkflow-xxxx
FrontendCloudFrontUrl https://d123456abcdef8.cloudfront.net
FrontendBucketName  crisis-pulse-prod-frontendbucket-xxxx
-------------------------------------------------------------------------------------------------
```

### Step 4: Configure & Deploy the Static Frontend
1. Update `frontend/config.js` with your deployed `ApiUrl`:
   ```javascript
   window.CRISIS_PULSE_CONFIG = {
     API_BASE_URL: "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod",
     POLL_INTERVAL_MS: 2000,
     MAX_POLL_ATTEMPTS: 25,
     MAX_IMAGE_SIZE_MB: 5,
   };
   ```
2. Upload the frontend files to the private S3 hosting bucket:
   ```bash
   aws s3 sync frontend/ s3://<FrontendBucketName>/ --delete
   ```
3. Open `FrontendCloudFrontUrl` in your browser (e.g. `https://d123456abcdef8.cloudfront.net`).  
   The site is securely served over HTTPS via CloudFront with S3 Origin Access Control (OAC).

---

## 🧪 End-to-End Operational Verification Runbook

Run these tests against your deployed `ApiUrl` using `curl` or Postman:

### 1. Health Liveness Check
```bash
curl -i https://<api-id>.execute-api.<region>.amazonaws.com/prod/health
```
**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "CrisisPulse",
  "timestamp": 1731672000,
  "version": "1.0.0",
  "demoMode": true
}
```

### 2. Request Presigned Photo Upload URL
```bash
curl -i -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/uploads \
  -H "Content-Type: application/json" \
  -d '{"filename": "scene.jpg", "contentType": "image/jpeg"}'
```
**Expected Response (201 Created):**
Returns `uploadUrl` and `photoKey` (e.g. `uploads/uuid.jpg`).

Upload a test JPEG image directly to S3:
```bash
curl -i -X PUT "<uploadUrl>" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@test-photo.jpg"
```
**Expected Response (200 OK):** S3 accepts the binary upload securely without public bucket access.

### 3. Create Incident Report & Trigger Step Functions
```bash
curl -i -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/incidents \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-run-001" \
  -d '{
    "category": "fire",
    "description": "Commercial building fire with active flames on 2nd floor.",
    "approximateLocation": "5th Ave & Pine St",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "riskFactors": ["active_fire", "life_threat"],
    "photoKey": "uploads/<your-photo-uuid>.jpg",
    "reporterName": "Jane Doe"
  }'
```
**Expected Response (201 Created):**
```json
{
  "incidentId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "Reported",
  "priority": "Critical",
  "createdAt": "2026-11-15T10:00:00Z"
}
```

Replaying the identical `Idempotency-Key` returns `200 OK` with `idempotentReplay: true` and creates no duplicate records.

### 4. Verify Step Functions Execution & Status Transition
Fetch the incident 3 seconds later:
```bash
curl -i https://<api-id>.execute-api.<region>.amazonaws.com/prod/incidents/3fa85f64-5717-4562-b3fc-2c963f66afa6
```
**Expected Result:**
- `status`: Automatically transitioned from `Reported` to `Under Review`.
- `priority`: `Critical` (score: `85/100`).
- `priorityExplanation`: Detailed breakdown of fire base points and risk factors.
- `statusHistory`: Contains timeline entries for both `Reported` and `Under Review`.
- `photoUrl`: Short-lived presigned GET URL to view the scene photo.

### 5. Verify Bounded Duplicate Detection (≤ 300m, 24h Window)
Submit a second report with the same category (`fire`) within 100 meters:
```bash
curl -i -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "category": "fire",
    "description": "Heavy smoke coming from building next door.",
    "approximateLocation": "5th Ave & Olive St",
    "latitude": 40.7135,
    "longitude": -74.0060
  }'
```
Wait 3 seconds and fetch the incident.  
**Expected Result:**
`isPotentialDuplicate: true`, `duplicateReason` references the first incident ID, and `duplicateCandidates` lists the distance (~77.8m).

### 6. Test Security & Unauthorized Status Rejections

CrisisPulse enforces strict authorization boundaries using **API Gateway HTTP API Cognito Authorizers** and backend validation:

#### A. Attempt Unauthenticated Descriptive Update (HTTP 401 Unauthorized)
```bash
curl -i -X PATCH https://<api-id>.execute-api.<region>.amazonaws.com/prod/incidents/<id> \
  -H "Content-Type: application/json" \
  -d '{"description": "Unauthorized attempt to modify description"}'
```
**Expected Response (401 Unauthorized):**
```json
{"error": "Unauthorized: Authentication required to modify incident reports. Please provide a valid Authorization Bearer token."}
```

#### B. Attempt Status Update on Incident Endpoint (HTTP 403 Forbidden)
Even with valid authentication, mutating incident lifecycle status via `/incidents/{id}` is permanently prohibited:
```bash
curl -i -X PATCH https://<api-id>.execute-api.<region>.amazonaws.com/prod/incidents/<id> \
  -H "Authorization: Bearer <valid-token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "Resolved"}'
```
**Expected Response (403 Forbidden):**
```json
{"error": "Forbidden: Incident status cannot be modified via /incidents/{id}. Status updates require coordinator authorization via /coordinator/incidents/{id}/status."}
```

#### C. Attempt Unauthenticated Coordinator Status Transition (HTTP 401 Unauthorized)
```bash
curl -i -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/coordinator/incidents/<id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "In Progress"}'
```
**Expected Response (401 Unauthorized):**
```json
{"error": "Unauthorized: Coordinator authorization required. Public users cannot modify incident status. For the weekend demonstration, configure Cognito User Pool authentication or execute status transitions directly via authenticated AWS Console operations."}
```

#### D. Authenticated Coordinator Transition (Cognito JWT / Demo Token)
To execute authorized status updates:

1. **Create an Emergency Coordinator in Cognito User Pool:**
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id <UserPoolId> \
     --username coordinator1 \
     --user-attributes Name=email,Value=coordinator@example.gov Name=email_verified,Value=true \
     --message-action SUPPRESS

   aws cognito-idp admin-set-user-password \
     --user-pool-id <UserPoolId> \
     --username coordinator1 \
     --password "CrisisCoord#2026!" \
     --permanent
   ```

2. **Acquire ID/Access Token:**
   ```bash
   aws cognito-idp initiate-auth \
     --auth-flow USER_PASSWORD_AUTH \
     --client-id <UserPoolClientId> \
     --auth-parameters USERNAME=coordinator1,PASSWORD="CrisisCoord#2026!"
   ```

3. **Call Protected Coordinator Endpoint:**
   ```bash
   curl -i -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/coordinator/incidents/<id>/status \
     -H "Authorization: Bearer <IdToken>" \
     -H "Content-Type: application/json" \
     -d '{"status": "In Progress", "notes": "Emergency response team dispatched to coordinates."}'
   ```
   *(For the weekend demo without Cognito setup, provide `-H "Authorization: Bearer demo-coordinator-secret-key-2026"`).*

---

## 🛠️ Troubleshooting Guide

| Issue / Symptom | Root Cause | Resolution |
| :--- | :--- | :--- |
| **CORS errors in browser** | Origin mismatch between client and API Gateway. | Ensure `FrontendOrigin` parameter in `sam deploy` matches your frontend domain (e.g. `https://d123456abcdef8.cloudfront.net` or `http://localhost:3000`). |
| **S3 Upload returns 403 Forbidden** | Expired presigned URL or mismatched `Content-Type`. | Ensure the upload `PUT` request uses the exact `Content-Type` specified when calling `POST /uploads` (e.g. `image/jpeg`). Presigned URLs expire after 300s. |
| **Step Functions fails on S3 photo validation** | Photo was not uploaded before incident submission, or `DemoMode` is false. | In testing environments, deploy with `DemoMode=true` to bypass physical S3 object checks. In production, upload the photo via the presigned URL before calling `POST /incidents`. |
| **HTTP 429 Too Many Requests** | API Gateway Throttling limit reached. | Default route settings throttle at 50 req/s with a burst of 100. Back off client requests exponentially. Increase limits in `template.yaml` if higher concurrency is required. |
| **DynamoDB Query fails on GSI** | GSI not fully backfilled or wrong index name. | Wait 60 seconds after initial deployment for GSIs (`createdAt-index` and `category-createdAt-index`) to reach `ACTIVE` state. |

---

## 💰 Estimated Cost Considerations (AWS Free Tier)

CrisisPulse uses AWS serverless pay-per-request services. There are **zero idle hourly server charges**:

- **Lambda**: 1,000,000 free requests/month, 3,200,000 seconds of compute.
- **DynamoDB**: 25 GB free storage, on-demand read/write operations free within standard allocations.
- **API Gateway HTTP API**: 1,000,000 free requests/month for the first 12 months.
- **Step Functions Standard**: 4,000 free state transitions/month.
- **S3 Standard**: 5 GB free storage, 20,000 GET requests, 2,000 PUT requests.
- **CloudFront**: 1 TB data transfer out/month and 10,000,000 free requests.

**Estimated monthly cost for prototype & demo usage: $0.00 / month.**

---

## 🧹 Complete Resource Teardown & Cleanup

To avoid unexpected charges after completing evaluation, delete all AWS resources:

```bash
# 1. Empty the S3 Photo Bucket (CloudFormation cannot delete non-empty buckets)
aws s3 rm s3://<PhotoBucketName> --recursive

# 2. Empty the S3 Frontend Bucket
aws s3 rm s3://<FrontendBucketName> --recursive

# 3. Delete the SAM CloudFormation Stack
sam delete --stack-name CrisisPulse-Prod

# 4. Note on DynamoDB:
# The DynamoDB table has `DeletionPolicy: Retain` to protect incident data against accidental loss.
# If you wish to delete the table permanently:
aws dynamodb delete-table --table-name <IncidentsTableName>
```

---

## 🧪 Local Automated Testing

Run the full automated test suite (all 46 tests) with a single command:

```bash
python run_tests.py
```

Validate the SAM template and CloudFormation architecture:

```bash
python tests/validate_sam.py
```

### Running the Frontend Locally

```bash
python start_frontend.py
```
This automatically starts a local static web server on port 3000 and opens `http://localhost:3000` in your browser. Configure `frontend/config.js` with your deployed `ApiUrl`.

---

## License
MIT

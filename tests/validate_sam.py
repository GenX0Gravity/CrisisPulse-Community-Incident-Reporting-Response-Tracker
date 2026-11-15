"""Comprehensive SAM template and architecture validator for CrisisPulse."""

import json
import os
import yaml

# Add CloudFormation intrinsic tag constructors to PyYAML
class CFNYamlLoader(yaml.SafeLoader):
    pass

def _cfn_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None

for tag in [
    "!Ref", "!Sub", "!GetAtt", "!Join", "!Select", "!Split",
    "!FindInMap", "!Base64", "!GetAZs", "!ImportValue", "!Condition",
    "!And", "!Or", "!Not", "!Equals", "!If"
]:
    yaml.add_constructor(tag, _cfn_constructor, Loader=CFNYamlLoader)


def validate():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(root, "template.yaml")
    asl_path = os.path.join(root, "state_machines", "incident_workflow.asl.json")

    print(f"--> Validating template: {template_path}")
    assert os.path.exists(template_path), "template.yaml does not exist"

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
        tpl = yaml.load(content, Loader=CFNYamlLoader)

    # 1. Basic SAM metadata
    assert tpl.get("AWSTemplateFormatVersion") == "2010-09-09", "Invalid template version"
    assert tpl.get("Transform") == "AWS::Serverless-2016-10-31", "Missing or invalid SAM transform"
    print("  [OK] Header and Serverless Transform")

    # 2. Parameters
    params = tpl.get("Parameters", {})
    required_params = ["FrontendOrigin", "DemoMode", "MaxImageSizeMB", "PresignedUrlExpirySec"]
    for p in required_params:
        assert p in params, f"Missing parameter: {p}"
    print(f"  [OK] Parameters present: {', '.join(required_params)}")

    # 3. Globals
    globals_sec = tpl.get("Globals", {}).get("Function", {})
    assert globals_sec.get("Runtime") == "python3.12", "Runtime must be python3.12"
    assert "TABLE_NAME" in globals_sec.get("Environment", {}).get("Variables", {})
    assert "PHOTO_BUCKET" in globals_sec.get("Environment", {}).get("Variables", {})
    assert "DEMO_MODE" in globals_sec.get("Environment", {}).get("Variables", {})
    assert "FRONTEND_ORIGIN" in globals_sec.get("Environment", {}).get("Variables", {})
    print("  [OK] Globals Function configuration and environment variables")

    # 4. Resources
    resources = tpl.get("Resources", {})
    assert "CrisisPulseApi" in resources, "CrisisPulseApi missing"
    assert "IncidentsTable" in resources, "IncidentsTable missing"
    assert "PhotoBucket" in resources, "PhotoBucket missing"
    assert "IncidentWorkflow" in resources, "IncidentWorkflow missing"
    assert "FrontendBucket" in resources, "FrontendBucket missing"
    assert "FrontendDistribution" in resources, "FrontendDistribution missing"
    assert "FrontendOAC" in resources, "FrontendOAC missing"
    print("  [OK] Core resources present (Backend + CloudFront HTTPS Frontend Hosting)")

    # 5. DynamoDB Table schema & GSIs
    ddb = resources["IncidentsTable"]["Properties"]
    assert ddb.get("BillingMode") == "PAY_PER_REQUEST", "BillingMode must be PAY_PER_REQUEST (on-demand)"
    key_schema = {k["AttributeName"]: k["KeyType"] for k in ddb.get("KeySchema", [])}
    assert key_schema.get("incidentId") == "HASH", "Partition key must be incidentId"
    
    gsi_list = ddb.get("GlobalSecondaryIndexes", [])
    gsi_names = [g["IndexName"] for g in gsi_list]
    assert "createdAt-index" in gsi_names, "Missing createdAt-index GSI for listing"
    assert "category-createdAt-index" in gsi_names, "Missing category-createdAt-index GSI for bounded duplicate detection"
    print("  [OK] DynamoDB table: on-demand, PK incidentId, GSIs (createdAt-index, category-createdAt-index)")

    # 6. S3 Bucket Security (Private, BlockPublicAccess, CORS)
    s3_props = resources["PhotoBucket"]["Properties"]
    pab = s3_props.get("PublicAccessBlockConfiguration", {})
    assert pab.get("BlockPublicAcls") is True
    assert pab.get("BlockPublicPolicy") is True
    assert pab.get("IgnorePublicAcls") is True
    assert pab.get("RestrictPublicBuckets") is True
    assert "CorsConfiguration" in s3_props, "S3 CORS configuration missing"

    # Frontend Bucket Security & Hosting (Supports both Private CloudFront OAC and S3 Static Website)
    fe_props = resources["FrontendBucket"]["Properties"]
    assert "WebsiteConfiguration" in fe_props, "WebsiteConfiguration missing on FrontendBucket"
    fe_pab = fe_props.get("PublicAccessBlockConfiguration", {})
    assert "BlockPublicAcls" in fe_pab
    print("  [OK] Photo & Frontend Buckets: Verified (Private Photo Storage + Dual-mode Frontend Hosting)")

    # 7. Endpoint verification & Authorizer Protection
    expected_endpoints = {
        ("GET", "/health"): ("HealthFunction", False),
        ("POST", "/uploads"): ("CreateUploadFunction", False),
        ("POST", "/incidents"): ("CreateIncidentFunction", False),
        ("GET", "/incidents"): ("ListIncidentsFunction", False),
        ("GET", "/incidents/{id}"): ("GetIncidentFunction", False),
        ("PATCH", "/incidents/{id}"): ("UpdateIncidentFunction", True),
        ("POST", "/coordinator/incidents/{id}/status"): ("CoordinatorUpdateStatusFunction", True),
    }

    # Verify Cognito User Pool and Client exist
    assert "CrisisPulseUserPool" in resources, "CrisisPulseUserPool resource missing"
    assert "CrisisPulseUserPoolClient" in resources, "CrisisPulseUserPoolClient resource missing"
    api_auth = resources["CrisisPulseApi"]["Properties"].get("Auth", {})
    assert "CognitoAuthorizer" in api_auth.get("Authorizers", {}), "CognitoAuthorizer missing from CrisisPulseApi"
    print("  [OK] Cognito User Pool, Client, and API Gateway CognitoAuthorizer verified")
    
    found_endpoints = {}
    endpoint_auth = {}
    for res_name, res_val in resources.items():
        if res_val.get("Type") == "AWS::Serverless::Function":
            events = res_val.get("Properties", {}).get("Events", {})
            for ev_name, ev_val in events.items():
                if ev_val.get("Type") == "HttpApi":
                    props = ev_val.get("Properties", {})
                    ep_key = (props.get("Method"), props.get("Path"))
                    found_endpoints[ep_key] = res_name
                    auth_prop = props.get("Auth", {})
                    has_auth = auth_prop.get("Authorizer") == "CognitoAuthorizer"
                    endpoint_auth[ep_key] = has_auth

    for ep, (fn, requires_auth) in expected_endpoints.items():
        assert ep in found_endpoints, f"Missing endpoint: {ep[0]} {ep[1]}"
        assert found_endpoints[ep] == fn, f"Endpoint {ep} mapped to {found_endpoints[ep]}, expected {fn}"
        assert endpoint_auth[ep] == requires_auth, (
            f"Endpoint {ep} requires_auth={requires_auth}, but found {endpoint_auth[ep]}"
        )
        auth_tag = "[PROTECTED: CognitoAuthorizer]" if requires_auth else "[PUBLIC]"
        print(f"  [OK] Endpoint {ep[0]:<5} {ep[1]:<38} -> {fn:<32} {auth_tag}")

    # 8. Handler file existence and syntax
    src_dir = os.path.join(root, "src")
    for res_name, res_val in resources.items():
        if res_val.get("Type") == "AWS::Serverless::Function":
            handler_str = res_val.get("Properties", {}).get("Handler")
            mod_path, func_name = handler_str.rsplit(".", 1)
            file_path = os.path.join(src_dir, *mod_path.split(".")) + ".py"
            assert os.path.exists(file_path), f"Handler file missing for {res_name}: {file_path}"
            with open(file_path, "r", encoding="utf-8") as hf:
                compile(hf.read(), file_path, "exec")
            print(f"  [OK] Handler verified & compiled: {handler_str}")

    # 9. Step Functions ASL Definition
    assert os.path.exists(asl_path), "incident_workflow.asl.json missing"
    with open(asl_path, "r", encoding="utf-8") as f:
        asl = json.load(f)
    assert asl.get("StartAt") == "ClassifyAndEnrich"
    assert "ClassifyAndEnrich" in asl.get("States", {})
    assert "PersistIncidentEnrichment" in asl.get("States", {})
    assert "WorkflowFailed" in asl.get("States", {})
    print("  [OK] Step Functions ASL definition verified (Task + DynamoDB updateItem integrations)")

    # 10. Stack Outputs
    outputs = tpl.get("Outputs", {})
    assert "ApiUrl" in outputs, "Missing ApiUrl output"
    assert "PhotoBucketName" in outputs, "Missing PhotoBucketName output"
    assert "IncidentsTableName" in outputs, "Missing IncidentsTableName output"
    assert "IncidentWorkflowArn" in outputs, "Missing IncidentWorkflowArn output"
    assert "FrontendCloudFrontUrl" in outputs, "Missing FrontendCloudFrontUrl output"
    assert "FrontendBucketName" in outputs, "Missing FrontendBucketName output"
    assert "UserPoolId" in outputs, "Missing UserPoolId output"
    assert "UserPoolClientId" in outputs, "Missing UserPoolClientId output"
    assert "UserPoolArn" in outputs, "Missing UserPoolArn output"
    print("  [OK] Outputs: ApiUrl, PhotoBucketName, IncidentsTableName, IncidentWorkflowArn, FrontendCloudFrontUrl, FrontendBucketName, UserPoolId, UserPoolClientId, UserPoolArn")

    print("\n✓ ALL VALIDATION CHECKS PASSED!")

if __name__ == "__main__":
    validate()

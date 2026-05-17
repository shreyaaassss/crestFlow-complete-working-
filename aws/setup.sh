#!/usr/bin/env bash
# =============================================================================
# CrestFlow Treasury — AWS Infrastructure Setup
# Run this ONCE to create all AWS resources. After this, GitHub Actions handles
# all deployments automatically on every push to master.
#
# Prerequisites:
#   - AWS CLI configured (aws configure) — already done
#   - Docker installed and running
#   - jq installed (brew install jq / apt install jq)
#
# Usage:
#   Fill in the REQUIRED SECRETS section below, then run:
#   chmod +x aws/setup.sh && bash aws/setup.sh
# =============================================================================

set -euo pipefail

# ─── AWS Config (pre-filled) ─────────────────────────────────────────────────
AWS_REGION="ap-south-1"
AWS_ACCOUNT_ID="385467777110"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ─── REQUIRED SECRETS — fill these in before running ─────────────────────────
# Never commit this file with real secrets filled in.

JWT_SECRET="${JWT_SECRET:-CHANGE_ME_strong_random_jwt_secret}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-CHANGE_ME}"
DEPLOYER_MNEMONIC="${DEPLOYER_MNEMONIC:-CHANGE_ME word1 word2 ...}"
ORCHESTRATOR_MNEMONIC="${ORCHESTRATOR_MNEMONIC:-CHANGE_ME word1 word2 ...}"
ADMIN_API_KEY="${ADMIN_API_KEY:-CHANGE_ME_strong_admin_key}"

# ─── Non-sensitive config (safe to edit here) ─────────────────────────────────
SUPABASE_URL="https://yetssyjyhmujmxefwxvh.supabase.co"
SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlldHNzeWp5aG11am14ZWZ3eHZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3MjUwODQsImV4cCI6MjA5NDMwMTA4NH0.FFTnyf3l1hWq_SzK_-G5cNwQoofXPbhvzJb7KX6Xfyk"
PLATFORM_WALLET="A2EGSHGIZMU7X6YRSLSC7GVDTXE6MAQCZODAWHWOVHLW6HCLOBJSTWLOFY"
ESCROW_APP_ID="762218790"
TBILL_APP_ID="762214340"
TBILL_1D_ASA="762214378"
TBILL_3D_ASA="762214379"
TBILL_7D_ASA="762214380"
TBILL_14D_ASA="762214381"
TBILL_30D_ASA="762214389"
TBILL_60D_ASA="762214390"
TBILL_90D_ASA="762214391"
NETWORK="testnet"
YIELD_BACKEND="reserve"
POLL_INTERVAL_MS="30000"
MIN_ORDER_AMOUNT_MICROALGO="5000000"

# ─── Validation ───────────────────────────────────────────────────────────────
if [[ "$JWT_SECRET" == CHANGE_ME* ]] || \
   [[ "$ORCHESTRATOR_MNEMONIC" == CHANGE_ME* ]]; then
  echo "ERROR: Fill in the REQUIRED SECRETS section before running this script."
  echo "       Set them as environment variables or edit the script directly."
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     CrestFlow Treasury — AWS Infrastructure Setup       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Account : $AWS_ACCOUNT_ID"
echo "Region  : $AWS_REGION"
echo ""

# ─── Helper ───────────────────────────────────────────────────────────────────
ok() { echo "  ✓ $*"; }
info() { echo "  → $*"; }
section() { echo ""; echo "── $* ──────────────────────────────────────────"; }

# =============================================================================
# 1. ECR Repositories
# =============================================================================
section "ECR Repositories"

for REPO in crestflow-backend crestflow-frontend crestflow-orchestrator; do
  if aws ecr describe-repositories --repository-names "$REPO" \
       --region "$AWS_REGION" &>/dev/null; then
    ok "ECR repo '$REPO' already exists"
  else
    aws ecr create-repository \
      --repository-name "$REPO" \
      --region "$AWS_REGION" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256 \
      --output json > /dev/null
    ok "Created ECR repo: $REPO"
  fi
done

# =============================================================================
# 2. SSM Parameter Store — secrets
# =============================================================================
section "SSM Parameter Store (secrets)"

put_ssm() {
  local NAME=$1 VALUE=$2
  aws ssm put-parameter \
    --name "/crestflow/$NAME" \
    --value "$VALUE" \
    --type SecureString \
    --overwrite \
    --region "$AWS_REGION" \
    --output json > /dev/null
  ok "SSM /crestflow/$NAME"
}

put_ssm "JWT_SECRET"                "$JWT_SECRET"
put_ssm "SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_SERVICE_ROLE_KEY"
put_ssm "DEPLOYER_MNEMONIC"         "$DEPLOYER_MNEMONIC"
put_ssm "ORCHESTRATOR_MNEMONIC"     "$ORCHESTRATOR_MNEMONIC"
put_ssm "ADMIN_API_KEY"             "$ADMIN_API_KEY"

# =============================================================================
# 3. IAM Role — App Runner ECR access
# =============================================================================
section "IAM Roles"

APPRUNNER_ROLE_NAME="crestflow-apprunner-ecr-role"
APPRUNNER_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${APPRUNNER_ROLE_NAME}"

if aws iam get-role --role-name "$APPRUNNER_ROLE_NAME" &>/dev/null; then
  ok "IAM role '$APPRUNNER_ROLE_NAME' already exists"
else
  aws iam create-role \
    --role-name "$APPRUNNER_ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "build.apprunner.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }]
    }' \
    --output json > /dev/null

  aws iam attach-role-policy \
    --role-name "$APPRUNNER_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"

  ok "Created IAM role: $APPRUNNER_ROLE_NAME"
fi

# ECS task execution role (for ECS Fargate + SSM secrets)
ECS_EXEC_ROLE_NAME="crestflow-ecs-execution-role"
ECS_EXEC_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ECS_EXEC_ROLE_NAME}"

if aws iam get-role --role-name "$ECS_EXEC_ROLE_NAME" &>/dev/null; then
  ok "IAM role '$ECS_EXEC_ROLE_NAME' already exists"
else
  aws iam create-role \
    --role-name "$ECS_EXEC_ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "ecs-tasks.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }]
    }' \
    --output json > /dev/null

  aws iam attach-role-policy \
    --role-name "$ECS_EXEC_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"

  # Allow ECS to read SSM SecureString parameters
  aws iam put-role-policy \
    --role-name "$ECS_EXEC_ROLE_NAME" \
    --policy-name "crestflow-ssm-read" \
    --policy-document "{
      \"Version\": \"2012-10-17\",
      \"Statement\": [{
        \"Effect\": \"Allow\",
        \"Action\": [\"ssm:GetParameters\", \"ssm:GetParameter\"],
        \"Resource\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/*\"
      }]
    }"

  ok "Created IAM role: $ECS_EXEC_ROLE_NAME"
fi

# =============================================================================
# 4. Build & Push Docker Images (initial push so App Runner can create services)
# =============================================================================
section "Docker — Initial Build & Push"

info "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

info "Building backend..."
docker build -t "$ECR_REGISTRY/crestflow-backend:latest" "$ROOT_DIR/backend"
docker push "$ECR_REGISTRY/crestflow-backend:latest"
ok "Pushed crestflow-backend:latest"

info "Building frontend (with placeholder API URL — update after step 5)..."
docker build \
  --build-arg VITE_API_URL="https://placeholder.ap-south-1.awsapprunner.com" \
  --build-arg VITE_SUPABASE_URL="$SUPABASE_URL" \
  --build-arg VITE_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
  --build-arg VITE_ADMIN_EMAIL="admin@crestflow.com" \
  -t "$ECR_REGISTRY/crestflow-frontend:latest" \
  "$ROOT_DIR/crest-flow-ui-main"
docker push "$ECR_REGISTRY/crestflow-frontend:latest"
ok "Pushed crestflow-frontend:latest"

info "Building orchestrator..."
docker build -t "$ECR_REGISTRY/crestflow-orchestrator:latest" "$ROOT_DIR/orchestrator"
docker push "$ECR_REGISTRY/crestflow-orchestrator:latest"
ok "Pushed crestflow-orchestrator:latest"

# =============================================================================
# 5. App Runner — Backend
# =============================================================================
section "App Runner — Backend"

BACKEND_SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='crestflow-backend'].ServiceArn" \
  --output text --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -n "$BACKEND_SERVICE_ARN" ] && [ "$BACKEND_SERVICE_ARN" != "None" ]; then
  ok "App Runner service 'crestflow-backend' already exists"
else
  info "Creating App Runner backend service..."
  BACKEND_SERVICE_ARN=$(aws apprunner create-service \
    --region "$AWS_REGION" \
    --service-name "crestflow-backend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"${ECR_REGISTRY}/crestflow-backend:latest\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"3001\",
          \"RuntimeEnvironmentVariables\": {
            \"NETWORK\":                   \"${NETWORK}\",
            \"BACKEND_PORT\":              \"3001\",
            \"ALGOD_SERVER\":              \"https://testnet-api.algonode.cloud\",
            \"ALGOD_PORT\":                \"443\",
            \"ALGOD_TOKEN\":               \"\",
            \"ESCROW_APP_ID\":             \"${ESCROW_APP_ID}\",
            \"TBILL_APP_ID\":              \"${TBILL_APP_ID}\",
            \"TBILL_1D_ASA\":              \"${TBILL_1D_ASA}\",
            \"TBILL_3D_ASA\":              \"${TBILL_3D_ASA}\",
            \"TBILL_7D_ASA\":              \"${TBILL_7D_ASA}\",
            \"TBILL_14D_ASA\":             \"${TBILL_14D_ASA}\",
            \"TBILL_30D_ASA\":             \"${TBILL_30D_ASA}\",
            \"TBILL_60D_ASA\":             \"${TBILL_60D_ASA}\",
            \"TBILL_90D_ASA\":             \"${TBILL_90D_ASA}\",
            \"PLATFORM_WALLET_ADDRESS\":   \"${PLATFORM_WALLET}\",
            \"SUPABASE_URL\":              \"${SUPABASE_URL}\",
            \"SUPABASE_ANON_KEY\":         \"${SUPABASE_ANON_KEY}\",
            \"YIELD_BACKEND\":             \"${YIELD_BACKEND}\"
          },
          \"RuntimeEnvironmentSecrets\": {
            \"JWT_SECRET\":                \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/JWT_SECRET\",
            \"SUPABASE_SERVICE_ROLE_KEY\":  \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/SUPABASE_SERVICE_ROLE_KEY\",
            \"DEPLOYER_MNEMONIC\":          \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/DEPLOYER_MNEMONIC\",
            \"ADMIN_API_KEY\":              \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/ADMIN_API_KEY\"
          }
        }
      },
      \"AutoDeploymentsEnabled\": false,
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"${APPRUNNER_ROLE_ARN}\"
      }
    }" \
    --instance-configuration '{"Cpu": "0.25 vCPU", "Memory": "0.5 GB"}' \
    --health-check-configuration '{"Protocol": "HTTP", "Path": "/health", "Interval": 10, "Timeout": 5, "HealthyThreshold": 1, "UnhealthyThreshold": 5}' \
    --query "Service.ServiceArn" \
    --output text)

  ok "Created App Runner backend: $BACKEND_SERVICE_ARN"
fi

info "Waiting for backend service URL..."
BACKEND_URL=$(aws apprunner describe-service \
  --service-arn "$BACKEND_SERVICE_ARN" \
  --query "Service.ServiceUrl" \
  --output text --region "$AWS_REGION")
BACKEND_URL="https://${BACKEND_URL}"
ok "Backend URL: $BACKEND_URL"

# =============================================================================
# 6. App Runner — Frontend (rebuild with real backend URL)
# =============================================================================
section "App Runner — Frontend"

info "Rebuilding frontend with backend URL: $BACKEND_URL"
docker build \
  --build-arg VITE_API_URL="$BACKEND_URL" \
  --build-arg VITE_SUPABASE_URL="$SUPABASE_URL" \
  --build-arg VITE_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
  --build-arg VITE_ADMIN_EMAIL="admin@crestflow.com" \
  -t "$ECR_REGISTRY/crestflow-frontend:latest" \
  "$ROOT_DIR/crest-flow-ui-main"
docker push "$ECR_REGISTRY/crestflow-frontend:latest"
ok "Frontend image rebuilt with correct backend URL"

FRONTEND_SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='crestflow-frontend'].ServiceArn" \
  --output text --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -n "$FRONTEND_SERVICE_ARN" ] && [ "$FRONTEND_SERVICE_ARN" != "None" ]; then
  ok "App Runner service 'crestflow-frontend' already exists"
  aws apprunner start-deployment --service-arn "$FRONTEND_SERVICE_ARN" \
    --region "$AWS_REGION" --output json > /dev/null
else
  info "Creating App Runner frontend service..."
  FRONTEND_SERVICE_ARN=$(aws apprunner create-service \
    --region "$AWS_REGION" \
    --service-name "crestflow-frontend" \
    --source-configuration "{
      \"ImageRepository\": {
        \"ImageIdentifier\": \"${ECR_REGISTRY}/crestflow-frontend:latest\",
        \"ImageRepositoryType\": \"ECR\",
        \"ImageConfiguration\": {
          \"Port\": \"3000\",
          \"RuntimeEnvironmentVariables\": {
            \"PORT\": \"3000\",
            \"NODE_ENV\": \"production\"
          }
        }
      },
      \"AutoDeploymentsEnabled\": false,
      \"AuthenticationConfiguration\": {
        \"AccessRoleArn\": \"${APPRUNNER_ROLE_ARN}\"
      }
    }" \
    --instance-configuration '{"Cpu": "0.25 vCPU", "Memory": "0.5 GB"}' \
    --health-check-configuration '{"Protocol": "HTTP", "Path": "/", "Interval": 10, "Timeout": 5, "HealthyThreshold": 1, "UnhealthyThreshold": 5}' \
    --query "Service.ServiceArn" \
    --output text)

  ok "Created App Runner frontend: $FRONTEND_SERVICE_ARN"
fi

info "Waiting for frontend service URL..."
FRONTEND_URL=$(aws apprunner describe-service \
  --service-arn "$FRONTEND_SERVICE_ARN" \
  --query "Service.ServiceUrl" \
  --output text --region "$AWS_REGION")
FRONTEND_URL="https://${FRONTEND_URL}"
ok "Frontend URL: $FRONTEND_URL"

# =============================================================================
# 7. Update Backend CORS with Frontend URL
# =============================================================================
section "Update Backend CORS"

info "Setting FRONTEND_URL on backend service..."
aws apprunner update-service \
  --service-arn "$BACKEND_SERVICE_ARN" \
  --region "$AWS_REGION" \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"${ECR_REGISTRY}/crestflow-backend:latest\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"3001\",
        \"RuntimeEnvironmentVariables\": {
          \"NETWORK\":                   \"${NETWORK}\",
          \"BACKEND_PORT\":              \"3001\",
          \"ALGOD_SERVER\":              \"https://testnet-api.algonode.cloud\",
          \"ALGOD_PORT\":                \"443\",
          \"ALGOD_TOKEN\":               \"\",
          \"ESCROW_APP_ID\":             \"${ESCROW_APP_ID}\",
          \"TBILL_APP_ID\":              \"${TBILL_APP_ID}\",
          \"TBILL_1D_ASA\":              \"${TBILL_1D_ASA}\",
          \"TBILL_3D_ASA\":              \"${TBILL_3D_ASA}\",
          \"TBILL_7D_ASA\":              \"${TBILL_7D_ASA}\",
          \"TBILL_14D_ASA\":             \"${TBILL_14D_ASA}\",
          \"TBILL_30D_ASA\":             \"${TBILL_30D_ASA}\",
          \"TBILL_60D_ASA\":             \"${TBILL_60D_ASA}\",
          \"TBILL_90D_ASA\":             \"${TBILL_90D_ASA}\",
          \"PLATFORM_WALLET_ADDRESS\":   \"${PLATFORM_WALLET}\",
          \"SUPABASE_URL\":              \"${SUPABASE_URL}\",
          \"SUPABASE_ANON_KEY\":         \"${SUPABASE_ANON_KEY}\",
          \"YIELD_BACKEND\":             \"${YIELD_BACKEND}\",
          \"FRONTEND_URL\":              \"${FRONTEND_URL}\"
        },
        \"RuntimeEnvironmentSecrets\": {
          \"JWT_SECRET\":                \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/JWT_SECRET\",
          \"SUPABASE_SERVICE_ROLE_KEY\":  \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/SUPABASE_SERVICE_ROLE_KEY\",
          \"DEPLOYER_MNEMONIC\":          \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/DEPLOYER_MNEMONIC\",
          \"ADMIN_API_KEY\":              \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/ADMIN_API_KEY\"
        }
      }
    },
    \"AutoDeploymentsEnabled\": false,
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"${APPRUNNER_ROLE_ARN}\"
    }
  }" \
  --output json > /dev/null
ok "Backend CORS updated with FRONTEND_URL=$FRONTEND_URL"

# =============================================================================
# 8. ECS Fargate — Orchestrator
# =============================================================================
section "ECS Fargate — Orchestrator"

# Create CloudWatch log group
aws logs create-log-group \
  --log-group-name "/ecs/crestflow-orchestrator" \
  --region "$AWS_REGION" 2>/dev/null || true
ok "CloudWatch log group: /ecs/crestflow-orchestrator"

# Create ECS cluster
if aws ecs describe-clusters --clusters crestflow-cluster \
     --region "$AWS_REGION" \
     --query "clusters[0].status" \
     --output text 2>/dev/null | grep -q "ACTIVE"; then
  ok "ECS cluster 'crestflow-cluster' already exists"
else
  aws ecs create-cluster \
    --cluster-name crestflow-cluster \
    --capacity-providers FARGATE \
    --region "$AWS_REGION" \
    --output json > /dev/null
  ok "Created ECS cluster: crestflow-cluster"
fi

# Get default VPC and first public subnet
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text --region "$AWS_REGION")

DEFAULT_SUBNET=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=${DEFAULT_VPC}" "Name=default-for-az,Values=true" \
  --query "Subnets[0].SubnetId" \
  --output text --region "$AWS_REGION")

ok "Using VPC: $DEFAULT_VPC  Subnet: $DEFAULT_SUBNET"

# Create security group for orchestrator (outbound HTTPS only)
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=crestflow-orchestrator-sg" \
            "Name=vpc-id,Values=${DEFAULT_VPC}" \
  --query "SecurityGroups[0].GroupId" \
  --output text --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "crestflow-orchestrator-sg" \
    --description "CrestFlow orchestrator — outbound only" \
    --vpc-id "$DEFAULT_VPC" \
    --region "$AWS_REGION" \
    --query "GroupId" \
    --output text)

  # Allow all outbound (Algorand API, Supabase)
  aws ec2 authorize-security-group-egress \
    --group-id "$SG_ID" \
    --protocol tcp --port 443 --cidr 0.0.0.0/0 \
    --region "$AWS_REGION" --output json > /dev/null 2>&1 || true

  ok "Created security group: $SG_ID"
else
  ok "Security group already exists: $SG_ID"
fi

# Register ECS task definition
info "Registering orchestrator task definition..."
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --region "$AWS_REGION" \
  --family crestflow-orchestrator \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 256 \
  --memory 512 \
  --execution-role-arn "$ECS_EXEC_ROLE_ARN" \
  --container-definitions "[{
    \"name\": \"orchestrator\",
    \"image\": \"${ECR_REGISTRY}/crestflow-orchestrator:latest\",
    \"essential\": true,
    \"environment\": [
      {\"name\": \"NETWORK\",                   \"value\": \"${NETWORK}\"},
      {\"name\": \"ALGOD_SERVER\",              \"value\": \"https://testnet-api.algonode.cloud\"},
      {\"name\": \"ALGOD_PORT\",                \"value\": \"443\"},
      {\"name\": \"ALGOD_TOKEN\",               \"value\": \"\"},
      {\"name\": \"ESCROW_APP_ID\",             \"value\": \"${ESCROW_APP_ID}\"},
      {\"name\": \"TBILL_APP_ID\",              \"value\": \"${TBILL_APP_ID}\"},
      {\"name\": \"TBILL_1D_ASA\",              \"value\": \"${TBILL_1D_ASA}\"},
      {\"name\": \"TBILL_3D_ASA\",              \"value\": \"${TBILL_3D_ASA}\"},
      {\"name\": \"TBILL_7D_ASA\",              \"value\": \"${TBILL_7D_ASA}\"},
      {\"name\": \"TBILL_14D_ASA\",             \"value\": \"${TBILL_14D_ASA}\"},
      {\"name\": \"TBILL_30D_ASA\",             \"value\": \"${TBILL_30D_ASA}\"},
      {\"name\": \"TBILL_60D_ASA\",             \"value\": \"${TBILL_60D_ASA}\"},
      {\"name\": \"TBILL_90D_ASA\",             \"value\": \"${TBILL_90D_ASA}\"},
      {\"name\": \"PLATFORM_WALLET_ADDRESS\",   \"value\": \"${PLATFORM_WALLET}\"},
      {\"name\": \"SUPABASE_URL\",              \"value\": \"${SUPABASE_URL}\"},
      {\"name\": \"SUPABASE_ANON_KEY\",         \"value\": \"${SUPABASE_ANON_KEY}\"},
      {\"name\": \"POLL_INTERVAL_MS\",          \"value\": \"${POLL_INTERVAL_MS}\"},
      {\"name\": \"MIN_ORDER_AMOUNT_MICROALGO\", \"value\": \"${MIN_ORDER_AMOUNT_MICROALGO}\"},
      {\"name\": \"YIELD_BACKEND\",             \"value\": \"${YIELD_BACKEND}\"}
    ],
    \"secrets\": [
      {\"name\": \"ORCHESTRATOR_MNEMONIC\",    \"valueFrom\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/ORCHESTRATOR_MNEMONIC\"},
      {\"name\": \"SUPABASE_SERVICE_ROLE_KEY\", \"valueFrom\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/crestflow/SUPABASE_SERVICE_ROLE_KEY\"}
    ],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\":         \"/ecs/crestflow-orchestrator\",
        \"awslogs-region\":        \"${AWS_REGION}\",
        \"awslogs-stream-prefix\": \"orchestrator\"
      }
    }
  }]" \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

ok "Task definition registered: $TASK_DEF_ARN"

# Create or update ECS service
EXISTING_SERVICE=$(aws ecs describe-services \
  --cluster crestflow-cluster \
  --services crestflow-orchestrator \
  --region "$AWS_REGION" \
  --query "services[0].status" \
  --output text 2>/dev/null || echo "")

if [ "$EXISTING_SERVICE" = "ACTIVE" ]; then
  aws ecs update-service \
    --cluster crestflow-cluster \
    --service crestflow-orchestrator \
    --task-definition "$TASK_DEF_ARN" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --output json > /dev/null
  ok "Updated ECS service: crestflow-orchestrator"
else
  aws ecs create-service \
    --cluster crestflow-cluster \
    --service-name crestflow-orchestrator \
    --task-definition "$TASK_DEF_ARN" \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "{
      \"awsvpcConfiguration\": {
        \"subnets\": [\"${DEFAULT_SUBNET}\"],
        \"securityGroups\": [\"${SG_ID}\"],
        \"assignPublicIp\": \"ENABLED\"
      }
    }" \
    --region "$AWS_REGION" \
    --output json > /dev/null
  ok "Created ECS service: crestflow-orchestrator"
fi

# =============================================================================
# Done — Print Summary & GitHub Secrets
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT COMPLETE                          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Backend  (App Runner) : $BACKEND_URL"
echo "  Frontend (App Runner) : $FRONTEND_URL"
echo "  Orchestrator (ECS)    : crestflow-cluster / crestflow-orchestrator"
echo ""
echo "── GitHub Secrets to set at:"
echo "   https://github.com/shreyaaassss/crestFlow-complete-working-/settings/secrets/actions"
echo ""
echo "  AWS_ACCESS_KEY_ID        = (your AWS access key)"
echo "  AWS_SECRET_ACCESS_KEY    = (your AWS secret key)"
echo "  JWT_SECRET               = $JWT_SECRET"
echo "  SUPABASE_SERVICE_ROLE_KEY= (your Supabase service role key)"
echo "  DEPLOYER_MNEMONIC        = (your deployer mnemonic)"
echo "  ORCHESTRATOR_MNEMONIC    = (your orchestrator mnemonic)"
echo "  ADMIN_API_KEY            = $ADMIN_API_KEY"
echo "  VITE_API_URL             = $BACKEND_URL"
echo "  VITE_SUPABASE_URL        = $SUPABASE_URL"
echo "  VITE_SUPABASE_ANON_KEY   = $SUPABASE_ANON_KEY"
echo "  VITE_ADMIN_EMAIL         = admin@crestflow.com"
echo ""
echo "After adding secrets, push to master to trigger the full CI/CD pipeline."
echo ""

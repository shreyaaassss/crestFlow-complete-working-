#!/usr/bin/env bash
# =============================================================================
# CrestFlow Treasury — AWS Infrastructure Setup (no Docker required)
#
# Creates ECR repos, IAM roles, ECS cluster, and ECS resources.
# GitHub Actions handles all Docker builds and App Runner deployments.
#
# Run once:
#   bash aws/setup.sh
# =============================================================================

set -euo pipefail
export MSYS_NO_PATHCONV=1  # Prevent Git Bash path mangling on Windows

AWS_REGION="ap-south-1"
AWS_ACCOUNT_ID="385467777110"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

ok()      { echo "  ✓ $*"; }
info()    { echo "  → $*"; }
section() { echo ""; echo "── $* ────────────────────────────────────────────"; }

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   CrestFlow — AWS Infrastructure Setup              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo "  Account : $AWS_ACCOUNT_ID  |  Region: $AWS_REGION"
echo ""

# =============================================================================
# 1. ECR Repositories
# =============================================================================
section "1. ECR Repositories"

for REPO in crestflow-backend crestflow-frontend crestflow-orchestrator; do
  if aws ecr describe-repositories --repository-names "$REPO" \
       --region "$AWS_REGION" &>/dev/null; then
    ok "ECR '$REPO' already exists"
  else
    aws ecr create-repository \
      --repository-name "$REPO" \
      --region "$AWS_REGION" \
      --image-scanning-configuration scanOnPush=true \
      --output json > /dev/null
    ok "Created ECR: $REPO"
  fi
done

# =============================================================================
# 2. IAM Roles
# =============================================================================
section "2. IAM Roles"

# App Runner — pulls images from ECR
APPRUNNER_ROLE_NAME="crestflow-apprunner-ecr-role"
if aws iam get-role --role-name "$APPRUNNER_ROLE_NAME" &>/dev/null; then
  ok "IAM role '$APPRUNNER_ROLE_NAME' already exists"
else
  aws iam create-role \
    --role-name "$APPRUNNER_ROLE_NAME" \
    --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --output json > /dev/null
  aws iam attach-role-policy \
    --role-name "$APPRUNNER_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  ok "Created: $APPRUNNER_ROLE_NAME"
fi

# ECS task execution — pulls ECR images + CloudWatch logs
ECS_EXEC_ROLE_NAME="crestflow-ecs-execution-role"
ECS_EXEC_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ECS_EXEC_ROLE_NAME}"

if aws iam get-role --role-name "$ECS_EXEC_ROLE_NAME" &>/dev/null; then
  ok "IAM role '$ECS_EXEC_ROLE_NAME' already exists"
else
  aws iam create-role \
    --role-name "$ECS_EXEC_ROLE_NAME" \
    --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --output json > /dev/null
  aws iam attach-role-policy \
    --role-name "$ECS_EXEC_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  ok "Created: $ECS_EXEC_ROLE_NAME"
fi

# =============================================================================
# 3. ECS Cluster + Networking
# =============================================================================
section "3. ECS Cluster"

aws logs create-log-group \
  --log-group-name "/ecs/crestflow-orchestrator" \
  --region "$AWS_REGION" 2>/dev/null || true
ok "CloudWatch log group: /ecs/crestflow-orchestrator"

if aws ecs describe-clusters --clusters crestflow-cluster \
     --region "$AWS_REGION" \
     --query "clusters[0].status" --output text 2>/dev/null | grep -q "ACTIVE"; then
  ok "ECS cluster 'crestflow-cluster' already active"
else
  aws ecs create-cluster \
    --cluster-name crestflow-cluster \
    --capacity-providers FARGATE \
    --region "$AWS_REGION" --output json > /dev/null
  ok "Created ECS cluster: crestflow-cluster"
fi

# Default VPC + subnet
DEFAULT_VPC=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text --region "$AWS_REGION")

DEFAULT_SUBNET=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=${DEFAULT_VPC}" "Name=default-for-az,Values=true" \
  --query "Subnets[0].SubnetId" --output text --region "$AWS_REGION")

ok "VPC: $DEFAULT_VPC  |  Subnet: $DEFAULT_SUBNET"

# Security group for orchestrator
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=crestflow-orchestrator-sg" \
            "Name=vpc-id,Values=${DEFAULT_VPC}" \
  --query "SecurityGroups[0].GroupId" --output text \
  --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "crestflow-orchestrator-sg" \
    --description "CrestFlow orchestrator - outbound only" \
    --vpc-id "$DEFAULT_VPC" \
    --region "$AWS_REGION" --query "GroupId" --output text)
  ok "Created security group: $SG_ID"
else
  ok "Security group: $SG_ID"
fi

# Save networking info for GitHub Actions reference
echo "$DEFAULT_SUBNET" > /tmp/crestflow-subnet.txt
echo "$SG_ID" > /tmp/crestflow-sg.txt

# =============================================================================
# 4. ECS Task Definition (placeholder image — GitHub Actions will update it)
# =============================================================================
section "4. ECS Task Definition (orchestrator)"

info "Registering initial task definition with placeholder image..."
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --region "$AWS_REGION" \
  --family crestflow-orchestrator \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 256 --memory 512 \
  --execution-role-arn "$ECS_EXEC_ROLE_ARN" \
  --container-definitions "[{
    \"name\": \"orchestrator\",
    \"image\": \"public.ecr.aws/docker/library/node:20-alpine\",
    \"essential\": true,
    \"command\": [\"sh\",\"-c\",\"echo 'Waiting for real image deploy via GitHub Actions' && sleep 3600\"],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\":         \"/ecs/crestflow-orchestrator\",
        \"awslogs-region\":        \"${AWS_REGION}\",
        \"awslogs-stream-prefix\": \"orchestrator\"
      }
    }
  }]" \
  --query "taskDefinition.taskDefinitionArn" --output text)
ok "Task definition: $TASK_DEF_ARN"

# =============================================================================
# 5. ECS Service
# =============================================================================
section "5. ECS Service (orchestrator)"

NET_CONFIG="{\"awsvpcConfiguration\":{\"subnets\":[\"${DEFAULT_SUBNET}\"],\"securityGroups\":[\"${SG_ID}\"],\"assignPublicIp\":\"ENABLED\"}}"

EXISTING=$(aws ecs describe-services \
  --cluster crestflow-cluster --services crestflow-orchestrator \
  --region "$AWS_REGION" --query "services[0].status" --output text 2>/dev/null || echo "")

if [ "$EXISTING" = "ACTIVE" ]; then
  ok "ECS service 'crestflow-orchestrator' already exists"
else
  aws ecs create-service \
    --cluster crestflow-cluster \
    --service-name crestflow-orchestrator \
    --task-definition "$TASK_DEF_ARN" \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "$NET_CONFIG" \
    --region "$AWS_REGION" --output json > /dev/null
  ok "Created ECS service: crestflow-orchestrator"
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           INFRASTRUCTURE READY — NEXT STEPS                 ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "  ECR repos, IAM roles, ECS cluster and service are ready."
echo "  App Runner services will be created by GitHub Actions on first push."
echo ""
echo "  1. Trigger the first deployment by pushing to master:"
echo "     git push target master"
echo ""
echo "  2. After the first deployment, get the backend App Runner URL from:"
echo "     https://ap-south-1.console.aws.amazon.com/apprunner"
echo "     Then update the GitHub Secret VITE_API_URL with that URL."
echo ""
echo "  3. Push again to trigger a frontend rebuild with the correct API URL."
echo ""
echo "  GitHub Actions: https://github.com/shreyaaassss/crestFlow-complete-working-/actions"
echo ""

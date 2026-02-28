#!/usr/bin/env bash
# Build Advista API Lambda image and push to ECR.
# Usage:
#   ./scripts/build-and-push-lambda.sh              # use default AWS profile
#   ./scripts/build-and-push-lambda.sh personal      # use profile "personal"
#   AWS_PROFILE=personal ./scripts/build-and-push-lambda.sh
# From repo root: Advista_api/scripts/build-and-push-lambda.sh [profile]
# ./scripts/build-and-push-lambda.sh personal
set -e

# Optional: first argument or AWS_PROFILE env (argument wins)
AWS_PROFILE="${1:-${AWS_PROFILE:-}}"
if [[ -n "${AWS_PROFILE}" ]]; then
  AWS_CMD="aws --profile ${AWS_PROFILE}"
  echo "Using AWS profile: ${AWS_PROFILE}"
else
  AWS_CMD="aws"
fi

ECR_REGISTRY="590184115599.dkr.ecr.ap-south-1.amazonaws.com"
ECR_REPO="advista/advista_api"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPO}"
REGION="ap-south-1"

# Run from Advista_api (where Dockerfile.lambda and pyproject.toml live)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${API_DIR}"

echo "Logging in to ECR..."
${AWS_CMD} ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# Build for Lambda: single platform, no attestations (avoids InvalidImage / extra manifests)
echo "Building image (Dockerfile.lambda) for linux/amd64 (Lambda compatibility)..."
docker build --platform linux/amd64 --provenance=false --sbom=false -f Dockerfile.lambda -t "${ECR_REPO}:latest" .

echo "Tagging for ECR..."
docker tag "${ECR_REPO}:latest" "${IMAGE_URI}:latest"

echo "Pushing to ${IMAGE_URI}..."
docker push "${IMAGE_URI}:latest"

echo "Done. Image: ${IMAGE_URI}:latest"

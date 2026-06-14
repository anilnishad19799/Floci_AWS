# Floci_AWS

Demo workspace for running local AWS-compatible workflows using Floci / LocalStack.

## Contents

- [Lambda demo](Floci_AWS/Lambda/README.md) — simple Lambda function with a FastAPI frontend.
- [ECR & ECS image-flip app](Floci_AWS/ECR_ECS/README.md) — Docker build, push to Floci ECR, and local ECS deployment guide.

## Prerequisites

- Docker
- Python 3.11+
- AWS CLI
- Floci or LocalStack running (default endpoint: `http://localhost:4566`)

## Quick start

1. Start Floci / LocalStack.
2. Run the Lambda demo: see [Floci_AWS/Lambda/README.md](Floci_AWS/Lambda/README.md).
3. Build and deploy the image-flip app: see [Floci_AWS/ECR_ECS/README.md](Floci_AWS/ECR_ECS/README.md).

## Useful commands

```bash
export LOCALSTACK_ENDPOINT=http://localhost:4566

# List Lambda functions
aws lambda list-functions --endpoint-url $LOCALSTACK_ENDPOINT

# List ECR repositories
aws ecr describe-repositories --endpoint-url $LOCALSTACK_ENDPOINT

# Show running Docker containers
docker ps
```

## Notes

- Replace placeholder host/ports and ARNs with values from your environment where needed.
- Want convenience scripts? I can add `deploy.sh` and `cleanup.sh` to automate common tasks.

---

If you'd like the helper scripts added, tell me which one to add first.

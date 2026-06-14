# Floci_AWS

A small demo workspace that shows how to build and run local AWS-compatible workflows using Floci/LocalStack.

Contents

- `Floci_AWS/Lambda/` — simple AWS Lambda example with a FastAPI frontend that invokes the Lambda.
- `Floci_AWS/ECR_ECS/` — Image Flip app: Docker build, push to local Floci ECR, and local ECS (Fargate-style) deployment guide.

Prerequisites

- Docker
- Python 3.11+
- AWS CLI (configured to use `--endpoint-url` for LocalStack/Floci)
- Floci or LocalStack running (default endpoint: `http://localhost:4566`)

Quick start

1. Start Floci/LocalStack.
2. Follow the instructions in `Floci_AWS/Lambda/README.md` to create and test the Lambda demo.
3. Follow the instructions in `Floci_AWS/ECR_ECS/README.md` to build the image-flip app, push to Floci ECR, and deploy to local ECS.

Useful commands

```bash
# LocalStack endpoint example
export LOCALSTACK_ENDPOINT=http://localhost:4566

# List Lambda functions in LocalStack
aws lambda list-functions --endpoint-url $LOCALSTACK_ENDPOINT

# List ECR repositories
aws ecr describe-repositories --endpoint-url $LOCALSTACK_ENDPOINT

# Inspect Docker containers
docker ps
```

Notes

- Replace placeholder host/ports and ARNs in each README with values from your environment when necessary.
- If you want, I can add convenience scripts (`deploy.sh`, `cleanup.sh`) to automate build/push/deploy and cleanup steps.

---

Happy hacking — tell me if you want the convenience scripts added.

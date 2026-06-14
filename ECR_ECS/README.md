# Image Flip App — Local Floci/ECR/ECS Guide

This repository contains a small FastAPI application (image-flip-app) and instructions to build, run, push to Floci ECR, and deploy locally to an ECS-like environment (Floci/LocalStack).

Table of contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Environment variables](#environment-variables)
- [Create local S3 buckets](#create-local-s3-buckets)
- [Project structure](#project-structure)
- [Local development (Docker)](#local-development-docker)
- [Push to Floci ECR](#push-to-floci-ecr)
- [Run from Floci ECR](#run-from-floci-ecr)
- [ECS: task, cluster & service](#ecs-task-cluster--service)
- [Verify & access the app](#verify--access-the-app)
- [Forceful cleanup (wipe workspace)](#forceful-cleanup-wipe-workspace)
- [Cleanup commands](#cleanup-commands)
- [Troubleshooting & notes](#troubleshooting--notes)

## Overview

The app accepts an uploaded image, flips it vertically, stores both original and flipped images in S3, and returns the object keys as JSON.

## Prerequisites

- Docker
- AWS CLI (you will use `--endpoint-url` for Floci/LocalStack)
- Floci / LocalStack running on `http://localhost:4566`
- Python 3.11+ (for local dev)

## Environment variables

Set these for convenience (example):

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export LOCALSTACK_ENDPOINT=http://localhost:4566
export ECR_HOST=localhost:5100

```

## Create local S3 buckets

```bash
aws s3 mb s3://image --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 mb s3://flip-image --endpoint-url $LOCALSTACK_ENDPOINT

# verify
aws s3 ls --endpoint-url $LOCALSTACK_ENDPOINT
```

## Project structure

Create `image-flip-app/` with the following layout:

```
image-flip-app/
├── app.py
├── requirements.txt
├── Dockerfile
└── templates/index.html
```

Example `requirements.txt`:

```
fastapi
uvicorn
jinja2
python-multipart
boto3
pillow
```

The `app.py` should configure `boto3` to use `$LOCALSTACK_ENDPOINT`, accept file uploads, store to `image`, flip the image, then store to `flip-image`.

Example `app.py` (complete):

```python
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse

import boto3
from PIL import Image
from io import BytesIO
import uuid

app = FastAPI()

templates = Jinja2Templates(directory="templates")

s3 = boto3.client(
  "s3",
  endpoint_url="http://host.docker.internal:4566",
  aws_access_key_id="test",
  aws_secret_access_key="test",
  region_name="us-east-1"
)

INPUT_BUCKET = "image"
OUTPUT_BUCKET = "flip-image"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
  return templates.TemplateResponse(
    request=request,
    name="index.html",
    context={"request": request}
  )

# Serve images directly from S3
@app.get("/image/{bucket}/{key}")
async def get_s3_image(bucket: str, key: str):
  s3_object = s3.get_object(Bucket=bucket, Key=key)
  return StreamingResponse(s3_object['Body'], media_type="image/jpeg")

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
  image_bytes = await file.read()
  image_key = str(uuid.uuid4()) + "-" + file.filename

  # Save original to S3 input bucket
  s3.put_object(Bucket=INPUT_BUCKET, Key=image_key, Body=image_bytes)

  # Flip image and save to S3 output bucket
  img = Image.open(BytesIO(image_bytes))
  flipped = img.transpose(Image.FLIP_TOP_BOTTOM)

  buffer = BytesIO()
  img_format = img.format if img.format else "JPEG"
  flipped.save(buffer, format=img_format)
  buffer.seek(0)

  flipped_key = "flipped-" + image_key
  s3.put_object(Bucket=OUTPUT_BUCKET, Key=flipped_key, Body=buffer.getvalue())

  return {
    "message": "success",
    "original": image_key,
    "flipped": flipped_key
  }
```

## Local development (Docker)

Build the image:

```bash
docker build -t image-flip-app .
```

Run locally:

```bash
docker run -p 8000:8000 image-flip-app
```

Open `http://localhost:8000` and upload an image.

## Push to Floci ECR

Create repository (Floci ECR emulation):

```bash
aws ecr create-repository --repository-name image-flip-repo --endpoint-url $LOCALSTACK_ENDPOINT
```

Get repository URI:

```bash
aws ecr describe-repositories --endpoint-url $LOCALSTACK_ENDPOINT
```

Tag & push image:

```bash
docker tag image-flip-app:latest $ECR_HOST/image-flip-repo:latest
docker push $ECR_HOST/image-flip-repo:latest
```

Verify:

```bash
aws ecr describe-images --repository-name image-flip-repo --endpoint-url $LOCALSTACK_ENDPOINT
```

## Run from Floci ECR

Pull & run:

```bash
docker pull $ECR_HOST/image-flip-repo:latest
docker run -p 8000:8000 $ECR_HOST/image-flip-repo:latest
```

## ECS: task, cluster & service

Create a cluster:

```bash
aws ecs create-cluster --cluster-name image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT
```

Register task definition (example):

```bash
aws ecs register-task-definition --endpoint-url $LOCALSTACK_ENDPOINT --cli-input-json '{
  "family": "image-flip-production-task",
  "networkMode": "bridge",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "image-flip-container",
      "image": "'$ECR_HOST'/image-flip-repo:latest",
      "essential": true,
      "portMappings": [ { "containerPort": 8000, "hostPort": 8000 } ],
      "environment": [ { "name": "INPUT_BUCKET", "value": "image" }, { "name": "OUTPUT_BUCKET", "value": "flip-image" } ]
    }
  ]
}'
```

Create service:

```bash
aws ecs create-service \
  --cluster image-flip-production-cluster \
  --service-name image-flip-service \
  --task-definition image-flip-production-task:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --endpoint-url $LOCALSTACK_ENDPOINT
```

## Verify & access the app

Get latest task ARN and describe it:

```bash
TASK_ARN=$(aws ecs list-tasks --cluster image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT --query "taskArns[-1]" --output text)
aws ecs describe-tasks --cluster image-flip-production-cluster --tasks $TASK_ARN --endpoint-url $LOCALSTACK_ENDPOINT
```

If the task runs as a Docker container locally, find container ID and internal IP:

```bash
docker ps | grep image-flip-app
docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" <CONTAINER_ID>
curl http://<CONTAINER_INTERNAL_IP>:8000/
```

## Forceful cleanup (wipe workspace)

Use these commands to completely reset the local workspace (containers, services, clusters, task defs, local ECR tags, images):

```bash
# stop/remove matching containers
docker stop $(docker ps -q --filter name=floci-ecs) || true
docker rm $(docker ps -a -q --filter name=floci-ecs) || true

# delete ECS service & cluster
aws ecs delete-service --cluster image-flip-production-cluster --service image-flip-service --force --endpoint-url $LOCALSTACK_ENDPOINT || true
aws ecs delete-cluster --cluster image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT || true

# deregister task definitions
aws ecs deregister-task-definition --task-definition image-flip-production-task:1 --endpoint-url $LOCALSTACK_ENDPOINT || true
aws ecs deregister-task-definition --task-definition image-flip-clean-task:1 --endpoint-url $LOCALSTACK_ENDPOINT || true

# remove local ECR tags and registry container (adjust ids/hosts)
docker rmi localhost:5100/image-flip-repo:latest || true
docker rmi localhost:4510/image-flip-repo:latest || true
docker rm -f 53609cf9c927 || true

# prune images and volumes
docker image prune -f
docker volume prune -f

# verification
docker ps | grep image-flip || true
docker images | grep image-flip || true
```

## Cleanup commands (selective)

```bash
aws ecs delete-service --cluster image-flip-production-cluster --service image-flip-service --force --endpoint-url $LOCALSTACK_ENDPOINT
aws ecs delete-cluster --cluster image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT
aws ecr delete-repository --repository-name image-flip-repo --force --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rm s3://image --recursive --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rm s3://flip-image --recursive --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rb s3://image --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rb s3://flip-image --endpoint-url $LOCALSTACK_ENDPOINT
```

## Troubleshooting & notes

- Ensure `$LOCALSTACK_ENDPOINT` matches your running Floci/LocalStack instance.
- When testing locally, `docker run` is the fastest iteration loop.
- Replace placeholder host/ports (`localhost:5100`, container IDs) with values from your environment when running commands.

---
```

## Verify ECS task and access the app

Get the latest running Task ARN:

```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster image-flip-production-cluster \
  --endpoint-url $LOCALSTACK_ENDPOINT \
  --query "taskArns[-1]" --output text)

aws ecs describe-tasks --cluster image-flip-production-cluster --tasks $TASK_ARN --endpoint-url $LOCALSTACK_ENDPOINT
```

If the task is running as a local Docker container, locate its container ID:

```bash
docker ps | grep image-flip-app
# Then inspect to get internal IP
docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" <CONTAINER_ID>
```

Curl the internal container IP on port 8000 to verify the app:

```bash
curl http://<CONTAINER_INTERNAL_IP>:8000/
```

Or if the service exposes the port on localhost, open http://localhost:8000

## Cleanup commands

Remove ECS service and cluster:

```bash
aws ecs delete-service --cluster image-flip-production-cluster --service image-flip-service --force --endpoint-url $LOCALSTACK_ENDPOINT
aws ecs delete-cluster --cluster image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT
```

Remove ECR repository (if desired):

```bash
aws ecr delete-repository --repository-name image-flip-repo --force --endpoint-url $LOCALSTACK_ENDPOINT
```

Remove S3 buckets and contents:

```bash
aws s3 rm s3://image --recursive --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rm s3://flip-image --recursive --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rb s3://image --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 rb s3://flip-image --endpoint-url $LOCALSTACK_ENDPOINT
```

## Troubleshooting & Notes

- If the app cannot reach S3, confirm `LOCALSTACK_ENDPOINT` and the `boto3` client configuration.
- When using Floci ECR, the host/port may differ (e.g. `localhost:5100`); use `aws ecr describe-repositories` to confirm the URI.
- If ECS tasks fail to start, describe the task with `aws ecs describe-tasks` to get logs and exit codes.
- When developing locally, running the Docker image directly (`docker run`) is faster for iterative testing.

If you want, I can also:
- add a simple `deploy.sh` script for pushing to Floci and creating the ECS service
- create minimal `app.py`, `requirements.txt`, and `Dockerfile` templates in the repo

---

## Forceful Workspace Cleanup (complete wipe)

Use the following steps when you want to fully reset your local Floci/LocalStack/ECS workspace and remove containers, services, task definitions, local ECR tags, and cached images. Run commands carefully — these remove containers and data.

1) Stop & remove running ECS containers (free port 8000):

```bash
# Stop any running containers whose name contains 'floci-ecs' (may return empty)
docker stop $(docker ps -q --filter name=floci-ecs) || true

# Remove stopped containers whose name contains 'floci-ecs'
docker rm $(docker ps -a -q --filter name=floci-ecs) || true
```

2) Delete ECS services and cluster metadata (LocalStack):

```bash
aws ecs delete-service \
  --cluster image-flip-production-cluster \
  --service image-flip-service \
  --force \
  --endpoint-url http://localhost:4566 || true

aws ecs delete-cluster \
  --cluster image-flip-production-cluster \
  --endpoint-url http://localhost:4566 || true
```

3) Deregister old task definitions:

```bash
aws ecs deregister-task-definition \
  --task-definition image-flip-production-task:1 \
  --endpoint-url http://localhost:4566 || true

aws ecs deregister-task-definition \
  --task-definition image-flip-clean-task:1 \
  --endpoint-url http://localhost:4566 || true
```

4) Remove local ECR tags and prune Docker images/volumes:

```bash
# Remove local ECR tags (adjust ports/hosts if different)
docker rmi localhost:5100/image-flip-repo:latest || true
docker rmi localhost:4510/image-flip-repo:latest || true

# Remove any specific registry container (force remove by container id)
docker rm -f 53609cf9c927 || true

# Remove dangling images and volumes
docker image prune -f
docker volume prune -f
```

5) Optional: remove dangling/unreferenced images by repository name and verify:

```bash
# List running image-flip containers (should be none)
docker ps | grep image-flip || true

# List image-flip images (should be none or only base images)
docker images | grep image-flip || true
```

Notes:

- Commands include `|| true` so scripts continue even if an item is already removed.
- Replace container IDs (e.g. `53609cf9c927`) with the actual container ID from `docker ps` when necessary.
- After cleanup, re-run the build/push/deploy steps in this README to recreate the environment from scratch.

If you'd like, I can add a `cleanup.sh` script to the repo that runs these steps with safety prompts. Would you like that?

# Describe task state
aws ecs describe-tasks \
  --cluster image-flip-production-cluster \
  --endpoint-url http://localhost:4566 \
  --tasks $TASK_ARN

  # 1. Locate the Container ID
docker ps | grep image-flip-app

# 2. Extract the Internal Network IP Address
docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" <CONTAINER_ID>

curl http://<CONTAINER_INTERNAL_IP>:8000/



Open
http://<CONTAINER_INTERNAL_IP>:8000/
Upload image
Expected flow:
Image Upload
      |
      v
S3 image bucket
      |
      v
Flip vertically
      |
      v
S3 flip-image bucket
      |
      v
Return JSON

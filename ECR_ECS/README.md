create s3
aws s3 mb s3://image
aws s3 mb s3://flip-image

check it is created or not
aws s3 ls


to see laupload list in s3

STEP 3 Create Project
mkdir image-flip-app

cd image-flip-app
Structure
image-flip-app
│
├── app.py
├── requirements.txt
├── Dockerfile
├── templates
│   └── index.html
└── uploads
STEP 4 requirements.txt
fastapi
uvicorn
jinja2
python-multipart
boto3
pillow
STEP 5 FastAPI Code
app.py
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

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
        "index.html",
        {"request": request}
    )

@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    image_bytes = await file.read()

    image_key = str(uuid.uuid4()) + "-" + file.filename

    s3.put_object(
        Bucket=INPUT_BUCKET,
        Key=image_key,
        Body=image_bytes
    )

    img = Image.open(BytesIO(image_bytes))

    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)

    buffer = BytesIO()

    flipped.save(buffer, format=img.format)

    buffer.seek(0)

    flipped_key = "flipped-" + image_key

    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=flipped_key,
        Body=buffer.getvalue()
    )

    return {
        "message": "success",
        "original": image_key,
        "flipped": flipped_key
    }
STEP 6 UI
templates/index.html
<!DOCTYPE html>
<html>
<head>
    <title>Image Flip</title>
</head>
<body>

<h2>Upload Image</h2>

<input type="file" id="imageFile">

<button onclick="upload()">
Upload
</button>

<pre id="result"></pre>

<script>

async function upload(){

    let file =
      document.getElementById("imageFile").files[0]

    let fd = new FormData()

    fd.append("file", file)

    let response = await fetch(
        "/upload",
        {
            method:"POST",
            body:fd
        }
    )

    let data = await response.json()

    document.getElementById("result")
    .innerText =
        JSON.stringify(data,null,2)
}

</script>
# Image Flip App — Local Floci/ECR/ECS Guide

This document describes how to build, run, and deploy the Image Flip application locally using Docker, Floci's ECR emulation, and a local ECS (Fargate-style) deployment.

Contents
- Overview
- Prerequisites
- Local S3 buckets
- App project structure
- Build & run locally (Docker)
- Verify S3 uploads
- Push image to Floci ECR
- Run from Floci ECR
- ECS: register task, create cluster & service
- Verify ECS task and access the app
- Cleanup & troubleshooting

## Overview

The Image Flip app is a small FastAPI service that accepts image uploads, flips them vertically using Pillow, writes the original and flipped images to S3, and returns JSON with the object keys.

## Prerequisites

- Docker installed and running
- `aws` CLI (configured to target Floci/LocalStack when needed)
- Floci/LocalStack running locally on `http://localhost:4566`
- Python 3.11+ for local development

Environment variables used in examples:

- `LOCALSTACK_ENDPOINT=http://localhost:4566`
- `ECR_HOST=localhost:5100` (example Floci ECR host)

## Create local S3 buckets

Create the input/output buckets used by the app:

```bash
LOCALSTACK_ENDPOINT=http://localhost:4566
aws s3 mb s3://image --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 mb s3://flip-image --endpoint-url $LOCALSTACK_ENDPOINT

# Verify
aws s3 ls --endpoint-url $LOCALSTACK_ENDPOINT
```

## App project structure

Create the project folder `image-flip-app` with the following files:

- `app.py` — FastAPI application
- `requirements.txt` — dependencies
- `Dockerfile` — container image build
- `templates/index.html` — simple upload UI

Example `requirements.txt`:

```
fastapi
uvicorn
jinja2
python-multipart
boto3
pillow
```

Example `app.py` (summary): the app reads uploaded file bytes, stores the original into `image` bucket, flips vertically and stores into `flip-image`, then returns JSON with keys. Configure `boto3` to use `$LOCALSTACK_ENDPOINT`.

## Build and run locally (Docker)

Build the image:

```bash
docker build -t image-flip-app .
```

Run the container locally:

```bash
docker run -p 8000:8000 image-flip-app
```

Open: http://localhost:8000 and upload an image.

## Verify S3 uploads

List the input/output buckets in LocalStack:

```bash
aws s3 ls s3://image --endpoint-url $LOCALSTACK_ENDPOINT
aws s3 ls s3://flip-image --endpoint-url $LOCALSTACK_ENDPOINT
```

You should see object keys like `uuid-filename.png` and `flipped-uuid-filename.png`.

## Push image to Floci ECR

Create ECR repository (Floci):

```bash
aws ecr create-repository --repository-name image-flip-repo --endpoint-url $LOCALSTACK_ENDPOINT
```

Get the repository URI:

```bash
aws ecr describe-repositories --endpoint-url $LOCALSTACK_ENDPOINT
# Example repository URI: $ECR_HOST/image-flip-repo
```

Tag the local image and push to Floci ECR:

```bash
docker tag image-flip-app:latest $ECR_HOST/image-flip-repo:latest
docker push $ECR_HOST/image-flip-repo:latest
```

Verify images in the repository:

```bash
aws ecr describe-images --repository-name image-flip-repo --endpoint-url $LOCALSTACK_ENDPOINT
```

## Run from Floci ECR (pull and run)

Pull and run the image from Floci ECR:

```bash
docker pull $ECR_HOST/image-flip-repo:latest
docker run -p 8000:8000 $ECR_HOST/image-flip-repo:latest
```

## ECS: Register task, create cluster and service

Create an ECS cluster:

```bash
aws ecs create-cluster --cluster-name image-flip-production-cluster --endpoint-url $LOCALSTACK_ENDPOINT
```

Register a task definition (example JSON inline). Replace `image` with the ECR image/tag or local image name if using Docker cache:

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
      "image": "localhost:5100/image-flip-repo:latest",
      "essential": true,
      "portMappings": [
        { "containerPort": 8000, "hostPort": 8000 }
      ],
      "environment": [
        { "name": "INPUT_BUCKET", "value": "image" },
        { "name": "OUTPUT_BUCKET", "value": "flip-image" }
      ]
    }
  ]
}'
```

Create a service for the task:

```bash
aws ecs create-service \
  --cluster image-flip-production-cluster \
  --service-name image-flip-service \
  --task-definition image-flip-production-task:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --endpoint-url $LOCALSTACK_ENDPOINT
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

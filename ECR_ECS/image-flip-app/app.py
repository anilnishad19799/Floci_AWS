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

# Serve images out of S3 directly to <img> tags
@app.get("/image/{bucket}/{key}")
async def get_s3_image(bucket: str, key: str):
    s3_object = s3.get_object(Bucket=bucket, Key=key)
    return StreamingResponse(s3_object['Body'], media_type="image/jpeg")

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image_key = str(uuid.uuid4()) + "-" + file.filename

    # 1. Save original to S3 input bucket
    s3.put_object(
        Bucket=INPUT_BUCKET,
        Key=image_key,
        Body=image_bytes
    )

    # 2. Flip image and save to S3 output bucket
    img = Image.open(BytesIO(image_bytes))
    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)

    buffer = BytesIO()
    img_format = img.format if img.format else "JPEG" 
    flipped.save(buffer, format=img_format)
    buffer.seek(0)

    flipped_key = "flipped-" + image_key
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=flipped_key,
        Body=buffer.getvalue()
    )

    # Return both keys so the frontend can map both images
    return {
        "message": "success",
        "original": image_key,
        "flipped": flipped_key
    }
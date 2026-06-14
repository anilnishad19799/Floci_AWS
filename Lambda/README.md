# Floci AWS Lambda Demo

This folder contains a simple AWS Lambda function and a FastAPI backend that invokes it using a local AWS Lambda endpoint.

## Files

- `lambda_function.py` - the Lambda handler implementation.
- `lambda_client.py` - the local AWS Lambda client using `boto3`.
- `app.py` - FastAPI app that calls the Lambda function.
- `function.zip` - zipped Lambda deployment package.

## Prerequisites

- Python 3.11+ installed.
- `boto3`, `fastapi`, and `uvicorn` installed.
- AWS CLI installed and configured, or LocalStack running on `http://localhost:4566`.
- A Lambda execution role ARN (for real AWS) or a dummy role ARN for LocalStack.

## Step-by-step setup

1. Open the folder `Floci_AWS/Lambda`.

2. Create `lambda_function.py` with the following content:

```python
# lambda_function.py

def lambda_handler(event, context):
    name = event.get("name", "Guest")
    return {
        "statusCode": 200,
        "message": f"Hello {name} from Floci Lambda"
    }
```

3. Create `lambda_client.py` with the following content:

```python
import json
import boto3

lambda_client = boto3.client(
    "lambda",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

def invoke_lambda(payload: dict):
    response = lambda_client.invoke(
        FunctionName="hello-lambda",
        InvocationType="RequestResponse",
        Payload=json.dumps(payload)
    )
    return json.loads(response["Payload"].read())
```

4. Create `app.py` with the following content:

```python
from fastapi import FastAPI
from lambda_client import invoke_lambda

app = FastAPI()

@app.get("/run")
def run(name: str):
    result = invoke_lambda({
        "name": name
    })
    return result
```

5. Zip the Lambda function package:

```bash
zip function.zip lambda_function.py
```

6. Create the Lambda function in LocalStack / AWS:

```bash
aws lambda create-function \
  --function-name hello-lambda \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::000000000000:role/dummy \
  --endpoint-url http://localhost:4566
```

> If you are using a real AWS account, replace the `--role` ARN with a valid IAM role ARN.

7. Start the FastAPI backend:

```bash
uvicorn app:app --reload
```

8. Test the FastAPI endpoint:

```bash
curl "http://localhost:8000/run?name=Anil"
```

9. Invoke the Lambda function directly through LocalStack:

```bash
curl \
  -X POST \
  http://localhost:4566/2015-03-31/functions/hello-lambda/invocations \
  -d '{"name": "Alice"}'
```

## Expected response

```json
{
  "statusCode": 200,
  "message": "Hello Anil from Floci Lambda"
}
```

## Notes

- `lambda_client.py` uses LocalStack endpoint `http://localhost:4566`.
- If you change the Lambda function name, update `FunctionName` in `lambda_client.invoke()`.
- The FastAPI app runs on port `8000` by default when started with `uvicorn`.
- To list all Lambda functions in LocalStack:

```bash
aws lambda list-functions --endpoint-url http://localhost:4566
```

- To delete the Lambda function in LocalStack:

```bash
aws lambda delete-function \
  --function-name hello-lambda \
  --endpoint-url http://localhost:4566
```

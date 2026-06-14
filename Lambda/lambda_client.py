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

    return json.loads(
        response["Payload"].read()
    )
from fastapi import FastAPI
from lambda_client import invoke_lambda

app = FastAPI()

@app.get("/run")
def run(name: str):

    result = invoke_lambda({
        "name": name
    })

    return result
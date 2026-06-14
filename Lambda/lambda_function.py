# lambda_function.py

def lambda_handler(event, context):

    name = event.get("name", "Guest")

    return {
        "statusCode": 200,
        "message": f"Hello {name} from Floci Lambda"
    }
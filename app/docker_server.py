import ollama
import psycopg2
from psycopg2 import Error
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import requests
import base64
import tempfile
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access environment variables
server = os.getenv("server")
database = os.getenv("database")
user = os.getenv("user")
password = os.getenv("password")


app = FastAPI()


# def OCR(image_bytes: bytes):
#     try:
#         encoded_image = base64.b64encode(image_bytes).decode("utf-8")
#         # Prepare the JSON payload
#         payload = {
#             "model": "qwen2.5vl:7b",
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": "show me all the text and number on the image",
#                     "images": [encoded_image],  # base64-encoded image
#                 }
#             ],
#             "stream": False,
#         }

#         # Send POST request to Ollama HTTP API
#         response = requests.post(
#             "http://host.docker.internal:11434/api/chat", json=payload
#         )

#         if response.status_code != 200:
#             raise RuntimeError(f"API error: {response.text}")

#         result = response.json()["message"]["content"]

#         with open(f"/app/server/text.txt", "w", encoding="utf-8") as f:
#             f.write(result)

#         return result

#     except Exception as e:
#         return f"An error occurred: {e}"
    
def OCR(image_bytes: bytes):
    try:
        # Save the image bytes to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        # Prepare multipart/form-data payload
        with open(tmp_path, "rb") as f:
            files = {"image": f}
            response = requests.post("http://host.docker.internal:4896/deepseek", files=files)

        if response.status_code != 200:
            raise RuntimeError(f"Server error: {response.text}")

        # Parse the FastAPI server’s JSON response
        result = response.json().get("result", "")

        # Optionally save output to file
        with open("server/text.txt", "w", encoding="utf-8") as f:
            f.write(result)

        return result

    except Exception as e:
        return f"An error occurred: {e}"


def summarize(content):

    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "system",
                "content": "You are a data extraction assistant that returns structured JSON only.",
            },
            {
                "role": "user",
                "content": f"""
                    {content}

                    Extract the following details and return ONLY in JSON format:

                    Expected JSON structure (array of objects):
                    [
                    {{
                        "DeliveryCompany": "string",
                        "ShipmentContent": "string",
                        "Quantity": integer,
                        "SenderName": "string",
                        "ReceiverName": "string",
                        "SenderAddress": "string",
                        "ReceiverAddress": "string",
                        "BarcodeNumber": ["string", "string", ...]  // all barcodes for this shipment go into this list
                    }}
                    ]

                    Rules:
                    - BarcodeNumber is order number/ shipping number. If found order number and shipping number add them both to BarcodeNumber.
                    - If multiple shipment contents exist, repeat the delivery company, sender, and receiver for each.
                    - If a shipment has multiple barcodes, put all barcode numbers in the **BarcodeNumber** list inside the same object.
                    - Do not include any text outside of JSON.
                    - Ensure valid JSON syntax.
                    """,
            },
        ],
        "stream": False,
    }

    # Send HTTP request to Ollama
    response2 = requests.post(
        "http://host.docker.internal:11434/api/chat", json=payload
    )

    # Convert HTTP response body (bytes) to Python dict
    data = response2.json()

    # Now safely extract the message content
    content2 = data["message"]["content"]

    # Write to file
    with open("/app/server/summary.json", "w", encoding="utf-8") as f:
        f.write(content2)

    return content2


def store_data():
    # Load JSON file
    with open("/app/server/summary.json") as f:
        items = json.load(f)
    """
    Store data into database

    Args:
    delivery_company (str): delivery company on the item
    shipment_content (str): the item that is shipped
    quantity (int): the quantity of the item
    sender (str): the sender of the item
    receiver (str): the receiver of the item
    """
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            dbname=database,
            user=user,
            password=password,
            host="host.docker.internal",
            port="5432",
        )

        # Create a cursor
        cur = conn.cursor()

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS invoice (
            id SERIAL PRIMARY KEY,
            delivery_company VARCHAR(100),
            shipment_content VARCHAR(300),
            quantity NUMERIC,
            sender VARCHAR(100),
            receiver VARCHAR(100),
            sender_address VARCHAR(300),
            receiver_address VARCHAR(300),
            barcode TEXT[] 
        )
        """
        )

        for item in items:
            print(item["ShipmentContent"])
            cur.execute(
                """
            INSERT INTO invoice (delivery_company, shipment_content,quantity,sender,receiver,sender_address, receiver_address, barcodes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    item["DeliveryCompany"],
                    item["ShipmentContent"],
                    item["Quantity"],
                    item["SenderName"],
                    item["ReceiverName"],
                    item.get("SenderAddress", ""),  # optional fallback
                    item.get("ReceiverAddress", ""),
                    item.get("BarcodeNumber", []),
                ),
            )

        conn.commit()
        return (
            "Query executed and committed successfully!",
            item["DeliveryCompany"],
            item["ShipmentContent"],
            item["Quantity"],
            item["SenderName"],
            item["ReceiverName"],
            item["SenderAddress"],
            item["ReceiverAddress"],
            item["BarcodeNumber"],
        )

    except Error as e:
        return ("Error occurred:", e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(None),
):
    try:
        if file:
            image_bytes = await file.read()
            content = OCR(image_bytes)
            print(content)
            summary = summarize(content)
            print(summary)
            result = store_data()
            print(result)
            return result
        else:
            raise HTTPException(status_code=400, detail="No image provided")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1234)

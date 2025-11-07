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
import re

# Load .env file
load_dotenv()

# Access environment variables
database = os.getenv("database")
user = os.getenv("user")
password = os.getenv("password")

app = FastAPI()


def ollama_ocr(image_bytes: bytes):
    try:
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        # Prepare the JSON payload
        payload = {
            "model": "qwen2.5vl:7b",
            "messages": [
                {
                    "role": "user",
                    "content": "show me all the text and number on the image",
                    "images": [encoded_image],  # base64-encoded image
                }
            ],
            "stream": False,
        }

        # Send POST request to Ollama HTTP API
        response = requests.post(
            "http://localhost:11434/api/chat", json=payload
        )

        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.text}")

        result = response.json()["message"]["content"]

        with open(f"server/text.txt", "w", encoding="utf-8") as f:
            f.write(result)

        return result

    except Exception as e:
        return f"An error occurred: {e}"
    
def deepseek_ocr(image_bytes: bytes):
    try:
        # Save the image bytes to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        # Prepare multipart/form-data payload
        with open(tmp_path, "rb") as f:
            files = {"image": f}
            response = requests.post("http://localhost:4896/deepseek", files=files)

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
    
def categorize(content):
    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "system",
                "content": """
                You are a categorizer that help to categorize invoice into different category, the category include shipment invoice and non shipment invoice.
                If there is shipping address means that it is shipment. 

                Under shipment and non shipment there are a few category:
                -clothes
                -meal
                -medicine
                
                If the item does not fall in any of the category, put misc

                
                rules:
                - only return category in json format:
                {"<shipment or non shipment>":"<category>"}

                """,
            },
            {
                "role": "user",
                "content": content,
            },
        ],
        "stream": False,
    }

    # Send HTTP request to Ollama
    response2 = requests.post(
        "http://localhost:11434/api/chat", json=payload
    )

    # Convert HTTP response body (bytes) to Python dict
    data2 = response2.json()

    # Now safely extract the message content
    content2 = data2["message"]["content"]


    return content2



def summarize_shipment(content,category):

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
                        "Category" : "string",
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

                    Input the category into the json: {category}

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
    response3 = requests.post(
        "http://localhost:11434/api/chat", json=payload
    )

    # Convert HTTP response body (bytes) to Python dict
    data3 = response3.json()

    # Now safely extract the message content
    content3 = data3["message"]["content"]

    # Write to file
    with open("server/shipment-summary.json", "w", encoding="utf-8") as f:
        f.write(content3)

    return content3

def clean_and_validate_json(raw_text: str):
    # 1. Remove Markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    text = re.sub(r"\s*```.*$", "", text.strip())

    # 2. Try to extract just the JSON portion
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        text = match.group(1)

    # 3. Validate JSON
    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError as e:
        print("Invalid JSON detected:", e)
        print("Raw text:\n", raw_text[:500])
        return None

def summarize_non_shipment(content,category):

    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "system",
                "content": f"""You are a data extraction assistant that returns structured JSON only.
                    
                    Extract the content provided and return ONLY in JSON format:

                    Expected JSON structure (array of objects):
                    [
                        {{
                            "Category": "string",
                            "Name": "string",  // name of the store
                            "Raw_data": "string" // all raw data from the receipt
                            "Total_Price": "string", // total price for all items
                            "SST": "string", // government tax
                            "Service_Charge" : "string" //service charge
                        }}
                    ]

                    Input the category into the json: {category}

                    Rules:
                    - You MUST follow exactly like the expected JSON structure
                    - If there are no barcodes, set "BarcodeNumber": [] (do NOT omit this key).
                    - Do not include any explanations, comments, or text before or after the JSON.
                """,
            },
            {
                "role": "user",
                "content": f"{content}",
            },
        ],
        "stream": False,
    }

        # Send HTTP request to Ollama
    response4 = requests.post(
        "http://localhost:11434/api/chat", json=payload
    )

    # Convert HTTP response body (bytes) to Python dict
    data4 = response4.json()

    # Now safely extract the message content
    content4 = data4["message"]["content"]

    
    parsed_json = clean_and_validate_json(content4)
    print(parsed_json)

    if parsed_json:
    # Write to file
        with open("server/non-shipment-summary.json", "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, ensure_ascii=False, indent=2)

    return content4




def store_shipment_data():
    # Load JSON file
    with open("server/shipment-summary.json") as f:
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
            host="localhost",
            port="5432",
        )

        # Create a cursor
        cur = conn.cursor()

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS shipment_invoice (
            id SERIAL PRIMARY KEY,
            category VARCHAR(100),
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

            cur.execute(
                """
            INSERT INTO shipment_invoice (category,delivery_company, shipment_content,quantity,sender,receiver,sender_address, receiver_address, barcode)
            VALUES (%s,%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    item["Category"],
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
            item["Category"],
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


def store_non_shipment_data():
    # Load JSON file
    with open("server/non-shipment-summary.json") as f:
        items = json.load(f)

    
    # Ensure `items` is always a list of dicts
    if isinstance(items, dict):
        items = [items]

    """
    Store data into database

    Args:
    name (str): name of the store
    items (str): the item bought
    quantity (int): the quantity of the item
    price (str): the price of the item
    """
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            dbname=database,
            user=user,
            password=password,
            host="localhost",
            port="5432",
        )

        # Create a cursor
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS non_shipment_invoice (
                id SERIAL PRIMARY KEY,
                category VARCHAR(100),
                name VARCHAR(100),
                raw_data VARCHAR(5000),
                total_price VARCHAR(100),
                SST VARCHAR(100),
                Service_Charge VARCHAR(100)
            )
        """)

        for item in items:

            cur.execute(
                """
                INSERT INTO non_shipment_invoice (category, name, raw_data, total_price, SST, Service_Charge)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    item["Category"],
                    item["Name"],
                    item["Raw_data"],
                    item["Total_Price"],
                    item["SST"],
                    item["Service_Charge"],
                ),
            )

        conn.commit()
        return (
            "Query executed and committed successfully!",
            item["Category"],
            item["Name"],
            item["Raw_data"],
            item["Total_Price"],
            item["SST"],
            item["Service_Charge"],
        )

    except Error as e:
        return ("Error occurred:", e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.post("/deepseek-ocr")
async def deepseek_ocr_endpoint(
    file: UploadFile = File(None),
):
    try:
        if file:
            image_bytes = await file.read()
            content = deepseek_ocr(image_bytes)
            print(content)
            category=categorize(content)
            print(category)
            data = json.loads(category) 
            if data.get("shipment"):
                print("sumarizing shipment")
                category=data["shipment"]
                summary = summarize_shipment(content,category)
                print(summary)
                result = store_shipment_data()
                print(result)
                return result
            
            elif data.get("non shipment"):
                print("sumarizing non shipment")
                category=data["non shipment"]
                summary = summarize_non_shipment(content,category)
                print(summary)
                result = store_non_shipment_data()
                print(result)
                return result
            else:
                return HTTPException(status_code=400, detail="no data provided")
        else:
            raise HTTPException(status_code=400, detail="No image provided")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/ollama-ocr")
async def ollama_ocr_endpoint(
    file: UploadFile = File(None),
):
    try:
        if file:
            image_bytes = await file.read()
            content = ollama_ocr(image_bytes)
            print(content)
            category=categorize(content)
            print(category)
            data = json.loads(category) 
            if data.get("shipment"):
                print("sumarizing shipment")
                category=data["shipment"]
                summary = summarize_shipment(content,category)
                print(summary)
                result = store_shipment_data()
                print(result)
                return result
            
            elif data.get("non shipment"):
                print("sumarizing non shipment")
                category=data["non shipment"]
                summary = summarize_non_shipment(content,category)
                print(summary)
                result = store_non_shipment_data()
                print(result)
                return result
            else:
                return HTTPException(status_code=400, detail="no data provided")
        else:
            raise HTTPException(status_code=400, detail="No image provided")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1234)

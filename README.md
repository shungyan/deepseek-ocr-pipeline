# 🧾 OCR Receipt Information Extractor

This project uses **DeepSeek-OCR (Optical Character Recognition)** to capture important information from receipts — such as barcodes, addresses, sender/receiver details, and item lists — and store them into a **PostgreSQL** database for structured storage and easy access.

---

## 🚀 Features
- Extracts key fields from receipt images using **DeepSeek OCR**
- Automatically identifies:
  - Barcode  
  - Sender & receiver details  
  - Addresses  
  - Purchased items  
- Stores parsed data in a PostgreSQL database
- Simple REST API for easy integration

---

## ⚙️ Prerequisites

Make sure you have the following installed:

- [Ollama](https://ollama.ai/)
- [UV](https://github.com/astral-sh/uv)
- [Docker](https://www.docker.com/)
- [PostgreSQL](https://www.postgresql.org/)

---

## 🧩 Setup Guide

### 1. Setup DeepSeek OCR

```bash
# Inside WSL
git clone https://github.com/shungyan/deepseek-ocr-pipeline
cd deepseek-ocr-pipeline/deepseek-ocr

# Create virtual environment
uv venv

# Install dependencies
pip install -r requirements.txt

# Run the OCR server
uv run server.py
```

---

### 2. Setup PostgreSQL

```bash
# Create a .env file in your project root
database=<your_database_name>
user=<your_username>
pasword=<your_password>
host=localhost
```

Make sure your PostgreSQL instance is running and accessible.

---

### 3. Build and Run OCR Docker Container

```bash
# Build Docker image
docker build -t ocr .

# Run OCR container
docker run -p 1234:1234 --name ocr -d --restart always ocr
```

---

### 4. Test the OCR API

You can test the endpoint using `curl`:

```bash
curl -X POST http://localhost:1234/ocr \
  -F "file=@~/Desktop/ocr/images/<receiptname>.jpeg"
```

---

## 🧠 Notes
- Ensure your OCR server (DeepSeek) and PostgreSQL are running before testing.
- You can modify the extraction logic in the OCR module to adapt to your specific receipt formats.

---

## 📜 License
This project is licensed under the **MIT License**.  
Feel free to use and modify it for your own applications.

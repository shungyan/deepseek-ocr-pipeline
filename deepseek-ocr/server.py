from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io
import uvicorn
from transformers import AutoModel, AutoTokenizer
import torch
import os
import io
import contextlib

os.environ["CUDA_VISIBLE_DEVICES"] = '0'
model_name = 'deepseek-ai/DeepSeek-OCR'


prompt = "Return all text on the image"
output_path = '.'

app = FastAPI(title="DeepSeek OCR API")

@app.post("/deepseek")
async def deepseek(image: UploadFile = File(...)): #prompt: str = Form("Free OCR.")):
    try:
        # Save the uploaded image temporarily
        temp_path = f"/tmp/{image.filename}"
        with open(temp_path, "wb") as f:
            f.write(await image.read())

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            model_name,
            _attn_implementation='flash_attention_2',
            trust_remote_code=True,
            use_safetensors=True,
            device_map="cuda:0"
        ).eval().cuda().to(torch.bfloat16)

        # Capture printed output
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer):
            model.infer(
                tokenizer,
                prompt=prompt,
                image_file=temp_path,
                output_path=output_path,
                base_size=1024,
                image_size=640,
                crop_mode=True,
                save_results=True,
                test_compress=True
            )

        printed_output = output_buffer.getvalue().strip()

        return JSONResponse({"result": printed_output or "No text captured."})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    

@app.get("/")
def root():
    return {"message": "DeepSeek OCR FastAPI server is running."}


if __name__ == "__main__":
    # Run FastAPI with Uvicorn directly
    uvicorn.run("server:app", host="0.0.0.0", port=4896, reload=True)

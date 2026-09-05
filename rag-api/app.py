from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()


@app.get("/")
def home():
    return {
        "message": "RAG API is running!"
    }


@app.get("/v1/models")
def get_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "n8n-rag",
                "object": "model",
                "created": 0,
                "owned_by": "local"
            }
        ]
    }


# -----------------------------
# OpenAI Chat API
# -----------------------------

class ChatRequest(BaseModel):
    model: str
    messages: list


@app.post("/v1/chat/completions")
def chat(request: ChatRequest):

    question = request.messages[-1]["content"]

    webhook = requests.post(
        "http://localhost:5678/webhook/44037686-a2d7-4bfa-a15f-ee6f1665bb8d",
        json={
            "question": question
        }
    )

    result = webhook.json()

    answer = result["answer"]
    sources = result.get("sources", [])

    if sources:
        answer += "\n\n---\n**Sources:**\n"
        answer += "\n".join(f"- {s}" for s in sources)

    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "created": 0,
        "model": "n8n-rag",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer
                },
                "finish_reason": "stop"
            }
        ]
    }
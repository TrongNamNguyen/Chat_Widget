from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello World!"}

@app.get("/greet/{name}")
def greet(name: str):
    return {"message": f"Hello {name}!"}

class Question(BaseModel):
    text: str

@app.post("/ask")
def ask(q: Question):
    return {"you_asked": q.text, "answer": "I don't know"}
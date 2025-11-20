from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.rag_engine import rag_service

router = APIRouter()

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    retrieved_image: str  
    page_number: int

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Receives a query, finds the relevant PDF page visually, 
    and returns the image + answer.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")


    image_b64, page_num = rag_service.search(request.query)
    
    if not image_b64:
        return ChatResponse(
            answer="Sorry, I couldn't find relevant information in the document.",
            retrieved_image="",
            page_number=0
        )

    ai_answer = rag_service.generate_answer(request.query, image_b64)

    return ChatResponse(
        answer=ai_answer,
        retrieved_image=image_b64,
        page_number=page_num
    )
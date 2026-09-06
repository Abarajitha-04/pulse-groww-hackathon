from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.models import ChatMessage, User
from app.schemas import ChatRequest, ChatResponse, ChatMessageOut
from app.services.chat_service import generate_reply

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")  # separate, looser than auth's limit but still bounded — each call is an LLM request
def send_message(
    request: Request, payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    reply, ai_generated = generate_reply(db, user, payload.message)
    return ChatResponse(reply=reply, ai_generated=ai_generated)


@router.get("/history", response_model=list[ChatMessageOut])
def get_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return rows


@router.delete("/history", status_code=204)
def clear_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete()
    db.commit()
    return None

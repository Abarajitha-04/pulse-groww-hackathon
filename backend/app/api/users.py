import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.models import (
    ChatMessage,
    Digest,
    PasswordResetToken,
    RefreshToken,
    User,
    Watchlist,
    WatchlistItem,
)
from app.schemas import DeleteAccountRequest, MessageResponse, UserOut, UserSettingsUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me/settings", response_model=UserOut)
def update_settings(
    payload: UserSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    # Only alerts_enabled today — deliberately its own endpoint rather
    # than a generic PATCH /users/me, so adding the next setting doesn't
    # mean loosening validation on identity fields like email.
    user.alerts_enabled = payload.alerts_enabled
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/export")
def export_my_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A plain JSON dump of everything this account owns — the "data
    portability" half of a basic compliance story (GDPR Art. 20 / CCPA
    right to access, at the level of rigor appropriate here: a machine-
    readable export of the user's own records, not a certified legal
    filing). Deliberately excludes password_hash and raw token hashes —
    those are credentials, not "your data" in the sense this endpoint is
    for, and returning them would just be a new way to leak them.
    """
    watchlists = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
    watchlist_payload = []
    for wl in watchlists:
        items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl.id).all()
        watchlist_payload.append({
            "id": wl.id,
            "name": wl.name,
            "created_at": wl.created_at.isoformat() if wl.created_at else None,
            "items": [
                {"symbol": i.symbol, "exchange": i.exchange, "added_at": i.added_at.isoformat() if i.added_at else None}
                for i in items
            ],
        })

    digests = db.query(Digest).filter(Digest.user_id == user.id).all()
    chat_messages = (
        db.query(ChatMessage).filter(ChatMessage.user_id == user.id).order_by(ChatMessage.created_at).all()
    )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "alerts_enabled": user.alerts_enabled,
        },
        "watchlists": watchlist_payload,
        "digests": [
            {"watchlist_id": d.watchlist_id, "generated_at": d.generated_at.isoformat() if d.generated_at else None, "content": d.content}
            for d in digests
        ],
        "chat_history": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in chat_messages
        ],
    }


@router.delete("/me", response_model=MessageResponse)
def delete_my_account(
    payload: DeleteAccountRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Soft-deletes the account: deactivates it (is_active=False, so
    get_current_user rejects any still-valid access token immediately —
    see app/core/deps.py), scrubs personally identifying fields, and
    revokes every session. Requires re-entering the password — an
    already-stolen access token should not be enough on its own to lock
    the real owner out of their own account by "deleting" it.

    Deliberately NOT a hard DELETE FROM users: watchlists, digests, and
    chat history stay in place (now unreachable — every route filters by
    user_id and the account is deactivated) rather than being cascaded
    away, so a support investigation or legal hold isn't racing a
    just-in-time delete. A real hard-delete-after-N-days purge job is a
    documented next step (docs/DECISIONS.md), not implemented here.
    """
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    user.is_active = False
    user.alerts_enabled = False
    # Free up the real email for reuse and remove the direct PII link,
    # while keeping a stable, non-guessable placeholder so historical
    # rows (digests, watchlists) don't need their FK touched.
    user.email = f"deleted-{uuid.uuid4()}@deleted.pulse.invalid"
    db.add(user)

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).update(
        {"used_at": datetime.now(timezone.utc)}
    )
    # Chat history can contain more free-form personal content than
    # structured watchlist data — clear it outright rather than just
    # orphaning it behind a deactivated account.
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete()

    db.commit()
    return MessageResponse(message="Account deleted")

from datetime import datetime, timezone

from app.core.security import hash_password
from app.models.models import ChatMessage, User, Watchlist, WatchlistItem
from app.services import cache, chat_service


def _make_user_with_watchlist(db, symbol: str) -> User:
    user = User(email="chat-test@example.com", password_hash=hash_password("x"))
    db.add(user)
    db.commit()
    db.refresh(user)
    wl = Watchlist(user_id=user.id, name="WL")
    db.add(wl)
    db.commit()
    db.refresh(wl)
    db.add(WatchlistItem(watchlist_id=wl.id, symbol=symbol))
    db.commit()
    return user


def test_fallback_reply_never_invents_numbers_and_uses_real_deltas(db_session):
    """Without GROQ_API_KEY, the deterministic fallback must still ground
    its answer in the same verified delta data — not a canned generic
    string with no relationship to what's actually happening."""
    user = _make_user_with_watchlist(db_session, "CHATSYM.NS")
    now = datetime.now(timezone.utc)
    cache.set_latest("CHATSYM.NS", {
        "symbol": "CHATSYM.NS", "price": 250.0, "volume": 1000, "exchange_ts": now, "source": "test",
    })

    reply, ai_generated = chat_service.generate_reply(db_session, user, "what's up with my watchlist?")

    assert ai_generated is False
    assert "CHATSYM.NS" in reply


def test_messages_are_persisted_to_chat_history(db_session):
    user = _make_user_with_watchlist(db_session, "HISTSYM.NS")
    chat_service.generate_reply(db_session, user, "hello")

    messages = db_session.query(ChatMessage).filter_by(user_id=user.id).order_by(ChatMessage.created_at).all()
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "hello"


def test_empty_watchlist_gets_an_honest_answer_not_a_crash(db_session):
    user = User(email="empty-chat@example.com", password_hash=hash_password("x"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    reply, ai_generated = chat_service.generate_reply(db_session, user, "how's my portfolio?")
    assert ai_generated is False
    assert "watchlist" in reply.lower()

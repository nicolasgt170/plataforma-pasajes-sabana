"""Autenticación administrativa con Argon2 y bloqueo temporal de 15 minutos."""
from datetime import datetime, timedelta

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdminUser, LoginAttempt

password_hasher = PasswordHash.recommended()
MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def authenticate_admin(db: Session, username: str, password: str) -> AdminUser | None:
    """Registra cada intento; no revela si el usuario existe ni registra contraseñas."""
    now = datetime.now()
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if user and user.locked_until and user.locked_until > now:
        db.add(LoginAttempt(username=username, failed_attempts=user.failed_attempts, status="BLOQUEADO", locked_at=user.locked_until))
        db.commit()
        return None
    if user and password_hasher.verify(password, user.password_hash):
        user.failed_attempts = 0
        user.locked_until = None
        db.add(LoginAttempt(username=username, failed_attempts=0, status="EXITOSO"))
        db.commit()
        return user
    attempts = (user.failed_attempts if user else 0) + 1
    locked_at = None
    status = "FALLIDO"
    if user:
        user.failed_attempts = attempts
        if attempts >= MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            locked_at = user.locked_until
            status = "BLOQUEADO"
    db.add(LoginAttempt(username=username, failed_attempts=attempts, status=status, locked_at=locked_at))
    db.commit()
    return None

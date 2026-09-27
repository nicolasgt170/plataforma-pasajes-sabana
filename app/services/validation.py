import re
from email.utils import parseaddr

from fastapi import HTTPException

NAME_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]{2,120}$")
DOCUMENT_RE = re.compile(r"^[A-Za-z0-9.-]{5,50}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
QR_RE = re.compile(r"^[A-Za-z0-9_\-=&?/:.]{8,500}$")


def clean_name(value: str, label: str = "El nombre") -> str:
    cleaned = " ".join(value.strip().split())
    if not NAME_RE.fullmatch(cleaned):
        raise HTTPException(400, detail=f"{label} no tiene un formato válido.")
    return cleaned


def clean_document(value: str) -> str:
    cleaned = value.strip()
    if not DOCUMENT_RE.fullmatch(cleaned):
        raise HTTPException(400, detail="El documento no tiene un formato válido.")
    return cleaned


def clean_email(value: str) -> str:
    cleaned = value.strip().lower()
    if len(cleaned) > 120 or parseaddr(cleaned)[1] != cleaned or "@" not in cleaned:
        raise HTTPException(400, detail="El correo electrónico no tiene un formato válido.")
    return cleaned


def clean_qr(value: str) -> str:
    cleaned = value.strip()
    if not QR_RE.fullmatch(cleaned):
        raise HTTPException(400, detail="El código QR no tiene un formato válido.")
    return cleaned

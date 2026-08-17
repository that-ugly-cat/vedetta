import bcrypt
from fastapi import Request
from db import get_user_by_id


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_current_user(request: Request):
    data = request.session.get("user")
    if not data:
        return None
    # re-validate against DB in case role changed
    user = get_user_by_id(data["id"])
    return user

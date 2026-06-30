from typing import Any

from jose import JWTError, jwt

from app.config import Settings
from app.core.exceptions import UnauthorizedError


def decode_supabase_jwt(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp", "iat"]},
        )
    except JWTError as exc:
        raise UnauthorizedError("Token inválido o expirado") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token sin identificador de usuario")

    role = payload.get("role", "authenticated")
    if role != "authenticated":
        raise UnauthorizedError("Token con rol no permitido")

    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": role,
        "claims": payload,
    }

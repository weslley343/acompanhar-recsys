import jwt
import os
from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Union, Literal
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")

class TokenPayload(BaseModel):
    id: Union[str, int]
    email: str
    role: Literal["admin", "professional", "responsible"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    """
    Equivalent to authMiddleware in Node.
    Extracts and verifies the JWT token.
    """
    try:
        # Note: In Node's jsonwebtoken, it's jwt.verify(token, secret)
        # In PyJWT, it's jwt.decode(token, secret, algorithms=["HS256"])
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Token verification failed")

def role_required(required_role: str):
    """
    Factory for role-based access control.
    """
    async def dependency(user: TokenPayload = Depends(get_current_user)):
        if user.role != required_role:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. {required_role.capitalize()} only."
            )
        return user
    return dependency

# Specific shortcuts like in the Node example
admin_only = role_required("admin")
professional_only = role_required("professional")
responsible_only = role_required("responsible")

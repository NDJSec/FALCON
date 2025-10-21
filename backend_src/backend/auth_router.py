from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.db_logger import SessionLocal, User
from backend.auth_utils import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.models import RegisterRequest, LoginRequest

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@auth_router.post("/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    username = request.username
    email = request.email
    password = request.password[:72]  # bcrypt max length

    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_active=True
    )
    db.add(new_user)
    db.commit()
    return {"status": "ok", "message": f"User '{username}' registered successfully"}


@auth_router.post("/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT."""
    username = request.username
    password = request.password[:72]  # bcrypt max length

    user = db.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


def get_user_from_token(request: Request, db: Session):
    """Extract user from Bearer token in Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split("Bearer ")[1]

    from backend.db_logger import _get_user_from_jwt
    user = _get_user_from_jwt(token, db)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    return user


@auth_router.get("/verify")
def verify_token(request: Request, db: Session = Depends(get_db)):
    """Verify JWT and return user info if valid."""
    user = get_user_from_token(request, db)
    return {
        "status": "ok",
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat(),
    }


@auth_router.get("/me")
def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Alias for /auth/verify for frontend convenience."""
    return verify_token(request, db)


@auth_router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    """
    Refresh the access token.
    Currently a simple stub: re-issues token for the same user.
    """
    user = get_user_from_token(request, db)
    # Re-issue token with a fresh expiration
    access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=60))
    return {"access_token": access_token, "token_type": "bearer"}

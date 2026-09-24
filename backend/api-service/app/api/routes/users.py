import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserOAuth, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Register a new user in the PostgreSQL users table."""
    normalized_email = payload.email.lower().strip()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role or "cpse_admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead, status_code=status.HTTP_200_OK)
async def login_user(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Verify credentials and return user profile from PostgreSQL."""
    normalized_email = payload.email.lower().strip()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return UserRead.model_validate(user)


@router.post("/oauth", response_model=UserRead, status_code=status.HTTP_200_OK)
async def sync_oauth_user(
    payload: UserOAuth,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Upsert Google OAuth user profile in PostgreSQL."""
    normalized_email = payload.email.lower().strip()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user:
        if payload.name and not user.full_name:
            user.full_name = payload.name
        if payload.role and not user.role:
            user.role = payload.role
        await db.commit()
        await db.refresh(user)
        return UserRead.model_validate(user)

    # Create new OAuth user with unusable password
    new_user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        full_name=payload.name,
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role=payload.role or "cpse_admin",
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserRead.model_validate(new_user)


@router.get("/by-email", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user_by_email(
    email: str = Query(..., description="User email address"),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Lookup user by email address from PostgreSQL."""
    stmt = select(User).where(func.lower(User.email) == email.lower().strip())
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead], status_code=status.HTTP_200_OK)
async def list_users(
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    """List all registered users from PostgreSQL."""
    stmt = select(User).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.get("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Get single user by UUID from PostgreSQL."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserRead.model_validate(user)

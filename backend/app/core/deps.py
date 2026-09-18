"""Authentication and authorization dependencies.

`get_current_user`  - any signed-in user
`require_admin`     - platform admins only
`resolve_scope`     - THE tenancy gate. An owner always gets their own
                      company's scope. An admin may pass ?scope_key= to view
                      another company; anyone else attempting that is refused.
"""
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.auth import ROLE_ADMIN, Company, User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to a live, active user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    claims = decode_token(authorization.split(" ", 1)[1].strip())
    if claims is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")

    try:
        user_id = int(claims.get("sub", ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session token.") from None

    # Re-read the user every request: a deactivated account must stop working
    # immediately, not when its token happens to expire.
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This account is no longer active.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=403, detail="Administrator access is required for this action."
        )
    return user


def resolve_scope(
    scope_key: str | None = Query(default=None, description="Admin only: view another company"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    """The single place tenancy is decided. Every data route depends on this."""
    if user.role == ROLE_ADMIN:
        # An admin with no scope_key sees the whole platform.
        return scope_key or "__ALL__"

    company = db.get(Company, user.company_id) if user.company_id else None
    if company is None or not company.is_active:
        raise HTTPException(
            status_code=403, detail="Your account is not linked to an active company."
        )

    # A non-admin asking for someone else's data is a hard refusal.
    if scope_key and scope_key != company.scope_key:
        raise HTTPException(
            status_code=403, detail="You can only access your own company's data."
        )
    return company.scope_key


def current_company(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Company | None:
    if not user.company_id:
        return None
    return db.get(Company, user.company_id)


def company_by_scope(db: Session, scope_key: str) -> Company | None:
    return db.scalar(select(Company).where(Company.scope_key == scope_key))

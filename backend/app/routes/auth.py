"""Registration, sign-in, and the admin company console.

Registration creates a COMPANY and its first OWNER together. There is no way
to self-register as an administrator - that role can only be granted by
bootstrapping the first admin from the server (see /api/auth/bootstrap-admin,
which refuses once any admin exists).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.logging import get_logger
from app.core.security import (
    create_token,
    hash_password,
    slugify_scope,
    validate_password,
    verify_password,
)
from app.db.session import get_db
from app.models.auth import ROLE_ADMIN, ROLE_OWNER, AuditLog, Company, User
from app.models.emission import EmissionRecord
from app.models.optimization import OptimizationRun

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)

MAX_FAILED_LOGINS = 8


# ------------------------------------------------------------------ schemas


class RegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=160)
    industry: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default="India", max_length=80)
    grid_zone: str | None = Field(default="IN-SO", max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


def _audit(db: Session, event: str, *, email: str | None = None, user_id: int | None = None,
           company_id: int | None = None, detail: str | None = None, success: bool = True) -> None:
    db.add(AuditLog(event=event, email=email, user_id=user_id, company_id=company_id,
                    detail=detail, success=success))
    db.commit()


def _user_payload(user: User, company: Company | None) -> dict:
    """What the client is allowed to know. Never includes the hash."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "company": None if company is None else {
            "id": company.id,
            "name": company.name,
            "scope_key": company.scope_key,
            "industry": company.industry,
            "country": company.country,
            "grid_zone": company.grid_zone,
        },
    }


# ----------------------------------------------------------------- register


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """Create a company and its owner account. Public."""
    problem = validate_password(payload.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        # Registration is public, so this does confirm the address is taken.
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    name = payload.company_name.strip()
    if db.scalar(select(Company).where(func.lower(Company.name) == name.lower())):
        raise HTTPException(
            status_code=409,
            detail=f"A company named '{name}' is already registered. Ask its owner to invite you.",
        )

    scope = slugify_scope(name)
    if db.scalar(select(Company).where(Company.scope_key == scope)):
        scope = f"{scope}-{int(datetime.now(timezone.utc).timestamp()) % 100000}"

    company = Company(
        name=name, scope_key=scope, industry=payload.industry,
        country=payload.country, grid_zone=payload.grid_zone,
    )
    db.add(company)
    db.flush()

    user = User(
        email=email, full_name=payload.full_name, password_hash=hash_password(payload.password),
        role=ROLE_OWNER, company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(company)

    _audit(db, "register", email=email, user_id=user.id, company_id=company.id,
           detail=f"Company '{name}' registered")

    token = create_token(user.id, user.email, user.role, user.company_id)
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(user, company)}


# -------------------------------------------------------------------- login


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    # One message for both "no such user" and "wrong password", so the endpoint
    # cannot be used to enumerate which emails are registered.
    invalid = HTTPException(status_code=401, detail="Incorrect email or password.")

    if user is None:
        _audit(db, "login_failed", email=email, detail="no such user", success=False)
        raise invalid

    if not user.is_active:
        _audit(db, "login_failed", email=email, user_id=user.id, detail="inactive", success=False)
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    if user.failed_logins >= MAX_FAILED_LOGINS:
        _audit(db, "login_blocked", email=email, user_id=user.id, success=False)
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Contact an administrator to unlock.",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_logins += 1
        db.commit()
        _audit(db, "login_failed", email=email, user_id=user.id,
               detail=f"bad password (attempt {user.failed_logins})", success=False)
        raise invalid

    user.failed_logins = 0
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    company = db.get(Company, user.company_id) if user.company_id else None
    _audit(db, "login", email=email, user_id=user.id, company_id=user.company_id)

    token = create_token(user.id, user.email, user.role, user.company_id)
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(user, company)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, user.company_id) if user.company_id else None
    return _user_payload(user, company)


# --------------------------------------------------------- admin bootstrap


class BootstrapRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    setup_key: str = Field(..., min_length=1)


@router.post("/bootstrap-admin", status_code=201)
def bootstrap_admin(payload: BootstrapRequest, db: Session = Depends(get_db)) -> dict:
    """Create the FIRST platform administrator.

    Refuses once any admin exists, and requires ADMIN_SETUP_KEY from the
    server environment - so this cannot be used to escalate privileges.
    """
    from app.core.config import get_settings

    configured = (get_settings().admin_setup_key or "").strip()
    if not configured:
        raise HTTPException(
            status_code=403,
            detail="ADMIN_SETUP_KEY is not set on the server, so admin bootstrap is disabled.",
        )
    if payload.setup_key != configured:
        _audit(db, "bootstrap_admin_failed", email=payload.email, success=False)
        raise HTTPException(status_code=403, detail="Invalid setup key.")

    if db.scalar(select(User).where(User.role == ROLE_ADMIN)):
        raise HTTPException(
            status_code=409,
            detail="An administrator already exists. Bootstrap can only be used once.",
        )

    problem = validate_password(payload.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="That email is already registered.")

    admin = User(email=email, full_name="Platform Administrator",
                 password_hash=hash_password(payload.password), role=ROLE_ADMIN, company_id=None)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    _audit(db, "bootstrap_admin", email=email, user_id=admin.id)

    token = create_token(admin.id, admin.email, admin.role, None)
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(admin, None)}


# ------------------------------------------------------------ admin console


@router.get("/admin/companies")
def list_companies(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    """Every company, with real usage counts. Admin only."""
    out = []
    for c in db.scalars(select(Company).order_by(Company.created_at.desc())).all():
        users = db.scalar(
            select(func.count()).select_from(User).where(User.company_id == c.id)
        ) or 0
        records = db.scalar(
            select(func.count()).select_from(EmissionRecord)
            .where(EmissionRecord.scope_key == c.scope_key)
        ) or 0
        runs = db.scalar(
            select(func.count()).select_from(OptimizationRun)
            .where(OptimizationRun.scope_key == c.scope_key)
        ) or 0
        total = db.scalar(
            select(func.coalesce(func.sum(EmissionRecord.co2e), 0.0))
            .where(EmissionRecord.scope_key == c.scope_key)
        ) or 0.0
        out.append({
            "id": c.id, "name": c.name, "scope_key": c.scope_key,
            "industry": c.industry, "country": c.country, "grid_zone": c.grid_zone,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "user_count": users, "record_count": records,
            "optimization_runs": runs, "total_co2e_kg": round(float(total), 2),
        })
    return out


@router.get("/admin/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    companies = {c.id: c.name for c in db.scalars(select(Company)).all()}
    return [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "company_id": u.company_id, "company_name": companies.get(u.company_id),
            "is_active": u.is_active, "failed_logins": u.failed_logins,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]


@router.post("/admin/companies/{company_id}/toggle")
def toggle_company(company_id: int, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict:
    c = db.get(Company, company_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found.")
    c.is_active = not c.is_active
    db.commit()
    _audit(db, "admin_toggle_company", email=admin.email, user_id=admin.id,
           company_id=c.id, detail=f"is_active -> {c.is_active}")
    return {"id": c.id, "name": c.name, "is_active": c.is_active}


@router.post("/admin/users/{user_id}/unlock")
def unlock_user(user_id: int, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    u.failed_logins = 0
    u.is_active = True
    db.commit()
    _audit(db, "admin_unlock_user", email=admin.email, user_id=admin.id, detail=f"unlocked {u.email}")
    return {"id": u.id, "email": u.email, "failed_logins": 0, "is_active": True}


@router.get("/admin/audit")
def audit_log(limit: int = 100, _: User = Depends(require_admin),
              db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id, "event": r.event, "email": r.email, "company_id": r.company_id,
            "detail": r.detail, "success": r.success,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

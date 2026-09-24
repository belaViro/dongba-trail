import hashlib
import hmac
import ipaddress
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select, update

from backend.app.errors import ApiError

from .models import Audit, LoginAttempt, SessionToken, Setting, User, now
from .schemas import Credentials, Setup, WechatLogin

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)
    return f"scrypt${salt}${result.hex()}"


def password_matches(password: str, hashed: str) -> bool:
    try:
        algorithm, salt, expected = hashed.split("$")
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)
        return algorithm == "scrypt" and hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def user_dict(user: User) -> dict:
    return {
        key: getattr(user, key)
        for key in ("id", "username", "display_name", "role", "merchant_id", "status", "created_at")
    }


def bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or len(header) > 300:
        raise ApiError(401, "AUTH_REQUIRED", "Login is required")
    return header[7:]


def current_user(request: Request) -> User:
    token = bearer(request)
    with request.app.state.database.session() as session:
        record = session.get(SessionToken, digest(token))
        if record is None or record.expires_at <= now():
            raise ApiError(401, "SESSION_EXPIRED", "Please log in again")
        user = session.get(User, record.user_id)
        if user is None or user.status != "active":
            raise ApiError(401, "ACCOUNT_UNAVAILABLE", "Account is unavailable")
        return user


def require_operations(user: User = Depends(current_user)) -> User:
    if user.role not in {"admin", "operator"}:
        raise ApiError(403, "FORBIDDEN", "Operations permission is required")
    return user


def require_merchant(user: User = Depends(current_user)) -> User:
    if user.role != "merchant" or not user.merchant_id:
        raise ApiError(403, "FORBIDDEN", "Merchant permission is required")
    return user


def token_response(session, user: User, settings) -> dict:
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(UTC) + timedelta(hours=getattr(settings, "session_hours", 24))
    session.add(
        SessionToken(token_hash=digest(token), user_id=user.id, expires_at=expiry.isoformat())
    )
    return {"access_token": token, "token_type": "bearer", "user": user_dict(user)}


def setup_allowed(request: Request) -> bool:
    settings = request.app.state.business_settings
    if not getattr(settings, "setup_enabled", False):
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        return False


@router.get("/setup-status")
def setup_status(request: Request):
    with request.app.state.database.session() as session:
        existing = session.scalar(select(User.id).where(User.role == "admin").limit(1))
        return {"setup_required": existing is None and setup_allowed(request)}


@router.post("/setup")
def setup(payload: Setup, request: Request):
    settings = request.app.state.business_settings
    if not setup_allowed(request):
        raise ApiError(403, "SETUP_DISABLED", "Initial setup is available locally only")
    secret = getattr(settings, "setup_secret", "")
    secret = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
    if getattr(settings, "environment", "development") == "production" and not secret:
        raise ApiError(403, "SETUP_DISABLED", "Production setup requires an explicit secret")
    if secret and not hmac.compare_digest(request.headers.get("X-Setup-Secret", ""), secret):
        raise ApiError(403, "SETUP_DISABLED", "Setup secret is invalid")
    with request.app.state.database.write() as session:
        sentinel = session.scalar(select(Setting).where(Setting.key == "setup").with_for_update())
        if sentinel is None:
            raise ApiError(503, "DATABASE_NOT_MIGRATED", "Apply database migrations first")
        if sentinel.value.get("complete") or session.scalar(
            select(User.id).where(User.role == "admin").limit(1)
        ):
            raise ApiError(409, "SETUP_COMPLETE", "Initial setup has already completed")
        user = User(
            username=payload.username,
            password_hash=password_hash(payload.password),
            display_name=payload.display_name,
            role="admin",
        )
        session.add(user)
        session.flush()
        sentinel.value = {"complete": True}
        session.add(Audit(user_id=user.id, action="setup", entity_type="users", entity_id=user.id))
        return token_response(session, user, settings)


@router.post("/login")
def login(payload: Credentials, request: Request):
    database = request.app.state.database
    attempt_key = digest(f"login:{request.client.host}:{payload.username.lower()}")
    # Persist failed attempts independently of the rejected authentication transaction.
    with database.write() as session:
        session.scalar(select(Setting).where(Setting.key == "setup").with_for_update())
        attempt = session.get(LoginAttempt, attempt_key)
        instant = datetime.now(UTC)
        if attempt and (instant - datetime.fromisoformat(attempt.started_at)).total_seconds() < 900:
            if attempt.count >= 10:
                raise ApiError(429, "LOGIN_RATE_LIMITED", "Try again after fifteen minutes")
            attempt.count += 1
        elif attempt:
            attempt.count, attempt.started_at = 1, now()
        else:
            session.add(LoginAttempt(key=attempt_key, count=1))
    with database.write() as session:
        user = session.scalar(select(User).where(User.username == payload.username))
        valid = password_matches(
            payload.password, user.password_hash if user else "scrypt$invalid$" + "0" * 128
        )
        if not valid or user is None or user.status != "active":
            raise ApiError(401, "INVALID_CREDENTIALS", "Username or password is incorrect")
        session.execute(update(LoginAttempt).where(LoginAttempt.key == attempt_key).values(count=0))
        return token_response(session, user, request.app.state.business_settings)


@router.post("/wechat")
async def wechat_login(payload: WechatLogin, request: Request):
    settings = request.app.state.business_settings
    if not payload.privacy_accepted:
        raise ApiError(400, "PRIVACY_REQUIRED", "Privacy consent is required")
    if not getattr(settings, "privacy_policy_published", False) or not getattr(
        settings, "privacy_contact", ""
    ):
        raise ApiError(503, "PRIVACY_NOT_PUBLISHED", "Privacy policy is not published")
    app_id = getattr(settings, "wechat_app_id", "")
    secret = getattr(settings, "wechat_app_secret", "")
    secret = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
    if not app_id or not secret:
        raise ApiError(503, "WECHAT_NOT_CONFIGURED", "WeChat login is not configured")
    try:
        async with httpx.AsyncClient(
            timeout=10,
            trust_env=False,
            transport=getattr(request.app.state, "wechat_transport", None),
        ) as client:
            response = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": app_id,
                    "secret": secret,
                    "js_code": payload.code,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(
            502, "WECHAT_UNAVAILABLE", "WeChat login is temporarily unavailable"
        ) from exc
    if not isinstance(result, dict) or result.get("errcode") or not result.get("openid"):
        raise ApiError(401, "WECHAT_CODE_INVALID", "WeChat login code is invalid or expired")
    username = "wx_" + digest(str(result["openid"]))
    with request.app.state.database.write() as session:
        # Serialize account creation using the persistent setup row on every database.
        session.scalar(select(Setting).where(Setting.key == "setup").with_for_update())
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, display_name="WeChat visitor", role="tourist")
            session.add(user)
            session.flush()
        if user.status != "active":
            raise ApiError(403, "ACCOUNT_UNAVAILABLE", "Account is unavailable")
        session.add(
            Audit(
                user_id=user.id,
                action="privacy_consent",
                entity_type="users",
                entity_id=user.id,
                detail={"version": getattr(settings, "privacy_version", "")},
            )
        )
        return token_response(session, user, settings)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.post("/logout")
def logout(request: Request, user: User = Depends(current_user)):
    with request.app.state.database.write() as session:
        session.execute(
            delete(SessionToken).where(SessionToken.token_hash == digest(bearer(request)))
        )
    return {"logged_out": True}

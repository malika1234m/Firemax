from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re
import uuid
import itertools
import time

E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")


class Organization(BaseModel):
    org_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Stripe billing state
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    plan: str = "trial"                      # "trial" | "starter" | "pro"
    subscription_status: str = "trialing"    # trialing | active | past_due | canceled | incomplete
    trial_ends_at: Optional[datetime] = None
    current_period_end: Optional[datetime] = None

    # Detection tuning — applied live to every camera in this org (see
    # detection/pipeline.py). confidence_threshold is the bar a detection
    # must clear to become an alert; alert_cooldown_seconds is the minimum
    # gap between two alerts on the same camera (prevents alert spam).
    confidence_threshold: float = 0.50
    alert_cooldown_seconds: int = 30

    # Per-org Home Assistant connection. Each customer runs their own HA on
    # their own site, so credentials are scoped to the org — never global.
    # The token is stored Fernet-encrypted (see crypto.py); ha_url is the
    # reachable base URL of that org's HA (e.g. their Nabu Casa cloud URL).
    ha_url: str = ""
    ha_token_encrypted: Optional[str] = None


class HAConfigUpdate(BaseModel):
    ha_url: str = Field(min_length=1)
    ha_token: str = Field(min_length=1)


class OrganizationPublic(BaseModel):
    org_id: str
    name: str
    plan: str
    subscription_status: str
    trial_ends_at: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    # "manual" when FiremeX staff set the plan by hand rather than it coming
    # from a payment provider. Exposed so the billing page can say "managed by
    # FiremeX" instead of showing an empty renewal date it will never have.
    plan_source: Optional[str] = None
    confidence_threshold: float = 0.50
    alert_cooldown_seconds: int = 30


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    confidence_threshold: Optional[float] = Field(None, ge=0.1, le=0.99)
    alert_cooldown_seconds: Optional[int] = Field(None, ge=5, le=600)


# Seat/camera ceilings per plan — enforced server-side on creation, not just
# shown as a UI hint. Keys must match Organization.plan values and the
# Stripe price lookup_keys used when bootstrapping products (see billing.py).
PLAN_LIMITS = {
    "trial":   {"max_cameras": 2,  "max_users": 3,   "label": "Trial"},
    "starter": {"max_cameras": 5,  "max_users": 10,  "label": "Starter"},
    "pro":     {"max_cameras": 50, "max_users": 100, "label": "Pro"},
}


class DetectionBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    confidence: float


class Camera(BaseModel):
    camera_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    name: str
    stream_url: str          # RTSP url or local video file path
    location: str = ""
    zone: str = "Unassigned"
    ip_address: str = ""
    resolution: str = "1080p"
    frame_rate: int = 30
    ai_tracking: bool = True
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CameraCreate(BaseModel):
    name: str
    stream_url: str
    location: str = ""
    zone: str = "Unassigned"
    ip_address: str = ""
    resolution: str = "1080p"
    frame_rate: int = 30
    ai_tracking: bool = True


_incident_seq = itertools.count(int(time.time()) % 9000 + 1000)


def _next_incident_code() -> str:
    return f"INC-{next(_incident_seq):04d}"


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_code: str = Field(default_factory=_next_incident_code)
    org_id: str
    camera_id: str
    camera_name: str
    hazard_type: str         # fire, smoke, camera_offline, etc.
    confidence: float
    zone: str = "Unassigned"
    status: str = "unresolved"      # unresolved | in_progress | resolved
    acknowledged: bool = False
    recipient: str = ""
    channel: str = "push"            # push | sms | email | sms/push | push/alarm ...
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    frame_b64: Optional[str] = None   # base64 JPEG snapshot

    # Human-in-the-loop escalation — automations (HA, Twilio) only fire once
    # an operator promotes a raw detection to a confirmed incident.
    promoted_to_incident: bool = False
    promoted_at: Optional[datetime] = None
    promoted_by: Optional[str] = None    # user_id of the operator who promoted it

    # Required when status is set to "resolved" — feeds back into model training.
    resolution_verdict: Optional[str] = None   # "true_fire" | "false_alarm"
    resolution_remark: Optional[str] = None
    resolved_by: Optional[str] = None    # user_id of the operator who resolved it
    resolved_at: Optional[datetime] = None


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    acknowledged: Optional[bool] = None
    resolution_verdict: Optional[str] = None
    resolution_remark: Optional[str] = None


class WSFrame(BaseModel):
    camera_id: str
    frame_b64: str           # base64 JPEG
    detections: list[DetectionBox]
    fps: float
    timestamp: str


class NotificationPrefs(BaseModel):
    push: bool = True
    sms: bool = True
    email: bool = False


class NotificationPrefsUpdate(BaseModel):
    push: Optional[bool] = None
    sms: Optional[bool] = None
    email: Optional[bool] = None


class User(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    name: str
    email: str
    password_hash: str
    role: str = "operator"     # "admin" | "operator"
    notification_prefs: NotificationPrefs = Field(default_factory=NotificationPrefs)
    # Bumped whenever the password changes/resets. The value is baked into
    # every issued JWT; a token whose version no longer matches is rejected,
    # so old sessions die the moment the password changes (see security.py).
    token_version: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserPublic(BaseModel):
    """User shape returned to clients — never includes password_hash."""
    user_id: str
    org_id: str
    name: str
    email: str
    role: str
    notification_prefs: NotificationPrefs = Field(default_factory=NotificationPrefs)
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TenantPlanUpdate(BaseModel):
    """Manual plan change applied by FiremeX staff from the platform console.

    This exists because billing is not live yet: without it, every tenant is
    stuck on whatever they signed up with and paid features cannot be granted
    at all. Once Stripe is the source of truth this stays useful for comps,
    trials extensions and support fixes — but a manual change is recorded as
    such (see plan_source) so a later webhook can be reconciled against it
    rather than silently overwriting a decision a human made.
    """
    plan: str
    # Defaults to "active" for a paid plan and "trialing" for the free one;
    # override only when you specifically need a different state.
    subscription_status: Optional[str] = None
    note: Optional[str] = Field(None, max_length=280)


class PlanUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1)
    price_usd: Optional[int] = Field(None, ge=0, le=100000)
    max_cameras: Optional[int] = Field(None, ge=1, le=100000)
    max_users: Optional[int] = Field(None, ge=1, le=100000)
    features: Optional[list[str]] = None


class Complaint(BaseModel):
    complaint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    org_name: str = ""
    user_id: str
    user_name: str = ""
    user_email: str = ""
    subject: str
    message: str
    category: str = "general"       # general | billing | detection | technical | other
    status: str = "open"            # open | in_progress | resolved
    staff_note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ComplaintCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    category: str = "general"


class ComplaintUpdate(BaseModel):
    status: Optional[str] = None      # open | in_progress | resolved
    staff_note: Optional[str] = None


class PlatformAdmin(BaseModel):
    """Internal FiremeX ops/devops identity — belongs to no customer org and
    monitors the whole platform. Stored in its own collection, separate from
    customer users."""
    admin_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# A site is "online" only while heartbeats keep arriving. The agent sends one
# every HEARTBEAT_INTERVAL seconds (default 10), so this allows several to be
# missed before declaring it down — long enough to ride out a blip, short
# enough that an operator isn't looking at a stale green dot.
SITE_OFFLINE_AFTER_SECONDS = 45


def effective_site_status(site: dict) -> str:
    """Status derived from last_seen_at, not from the stored flag.

    The stored flag is written "online" by the heartbeat and NOTHING ever writes
    it back — so a site whose agent died stayed Online indefinitely. In a
    life-safety product that is the worst possible direction to be wrong in: the
    dashboard tells an operator a building is monitored when nothing is running.

    Derivation is used rather than a background sweeper because it cannot drift,
    needs no scheduler, and is correct the instant it is read.
    """
    if not site.get("last_seen_at"):
        return "pending"          # enrolled but no agent has ever connected
    age = (datetime.utcnow() - site["last_seen_at"]).total_seconds()
    return "online" if age <= SITE_OFFLINE_AFTER_SECONDS else "offline"


class Site(BaseModel):
    """A physical customer site running an edge agent. The agent reads local
    cameras, runs detection on the customer's own hardware, and reports events
    up to the cloud — so camera video never leaves the customer's network.
    The enrollment token is stored hashed; the raw value is shown once."""
    site_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    name: str
    token_hash: str
    status: str = "pending"          # pending | online | offline
    agent_version: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SitePublic(BaseModel):
    site_id: str
    org_id: str
    name: str
    status: str
    agent_version: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime


# ── Edge-agent → cloud payloads ─────────────────────────────────────────────

class AgentPipelineHealth(BaseModel):
    camera_id: str
    fps: float = 0.0
    inference_ms: float = 0.0
    online: bool = False
    last_frame_age_s: Optional[float] = None


class AgentHeartbeat(BaseModel):
    agent_version: Optional[str] = None
    pipelines: list[AgentPipelineHealth] = Field(default_factory=list)


class AgentEvent(BaseModel):
    camera_id: str
    camera_name: str
    hazard_type: str
    confidence: float
    zone: str = "Unassigned"
    frame_b64: Optional[str] = None


class PasswordResetToken(BaseModel):
    token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, description="Creates a brand-new organization; you become its admin.")
    name: str
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreateByAdmin(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)
    role: str = "operator"      # "admin" | "operator"


class UserRoleUpdate(BaseModel):
    role: str      # "admin" | "operator"


class Shift(BaseModel):
    shift_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    user_id: str
    user_name: str
    start_time: datetime
    end_time: datetime
    label: str = ""       # e.g. "Morning", "Night"
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ShiftCreate(BaseModel):
    user_id: str
    start_time: datetime
    end_time: datetime
    label: str = ""
    notes: str = ""


class AuthorityContact(BaseModel):
    contact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    name: str
    phone: str
    notify_via: str = "sms"     # "sms" | "call" | "both"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuthorityContactCreate(BaseModel):
    name: str
    phone: str
    notify_via: str = "sms"

    @field_validator("phone")
    @classmethod
    def phone_must_be_e164(cls, v: str) -> str:
        if not E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format, e.g. +15551234567")
        return v


class DemoRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    company: str
    phone: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DemoRequestCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    company: str = Field(min_length=1)
    phone: Optional[str] = None
    message: Optional[str] = None

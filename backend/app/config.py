from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "development" | "production". Setting this to "production" turns the
    # startup warnings below into hard failures — the server refuses to boot
    # with placeholder secrets or plaintext URLs (see main.py). Deliberate:
    # a fire-detection system silently running on a publicly-known JWT key is
    # worse than one that won't start.
    ENVIRONMENT: str = "development"

    MONGODB_URL: str = "mongodb://localhost:27017"
    DB_NAME: str = "firemax"

    # Path to your YOLOv8 fire/hazard model weights
    # Download a fire model from: https://universe.roboflow.com (search "fire detection")
    # or use "yolov8n.pt" for the default COCO model to test the pipeline
    MODEL_PATH: str = "models/fire_model.pt"
    CONFIDENCE_THRESHOLD: float = 0.50
    PROCESS_FPS: int = 5  # frames per second sent to ML (not display FPS)

    # Home Assistant integration
    HA_URL:        str = ""   # e.g. http://homeassistant:8123
    HA_TOKEN:      str = ""   # long-lived access token from HA profile
    HA_WEBHOOK_ID: str = "firemax_hazard_alert"

    # Email alerts (optional)
    SMTP_HOST:  str = ""
    SMTP_PORT:  int = 587
    SMTP_USER:  str = ""
    SMTP_PASS:  str = ""
    ALERT_EMAIL:str = ""
    SALES_EMAIL:str = ""   # where "Request a Demo" submissions are emailed; falls back to ALERT_EMAIL if unset

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Auth
    JWT_SECRET:       str = "dev-insecure-secret-change-me"
    JWT_EXPIRE_HOURS:  int = 24
    COOKIE_SECURE:    bool = False   # set True once served over HTTPS

    # Rate limiting. REDIS_URL enables a shared sliding-window store (required
    # once you run more than one instance / behind a load balancer); leave
    # blank to fall back to a process-local limiter for single-instance dev.
    REDIS_URL: str = ""
    # How many reverse proxies sit in front of the app. The client IP is taken
    # from that many hops back in X-Forwarded-For; 0 means trust no proxy and
    # use the socket peer (correct when nothing fronts the app). NEVER set this
    # higher than your real proxy depth or clients can spoof their IP.
    TRUSTED_PROXY_COUNT: int = 0

    # Fernet key (44-char urlsafe base64) used to encrypt per-org secrets such
    # as Home Assistant tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRETS_ENCRYPTION_KEY: str = ""

    # Platform (vendor) super-admin — internal FiremeX ops team only, NOT a
    # customer. If both are set, a platform admin with this email is created on
    # startup. This identity monitors the whole fleet across all tenants and is
    # deliberately kept off the customer surface (separate login + cookie).
    PLATFORM_ADMIN_EMAIL:    str = ""
    PLATFORM_ADMIN_PASSWORD: str = ""

    # Twilio (authority call/SMS on incident promotion)
    TWILIO_ACCOUNT_SID:  str = ""
    TWILIO_AUTH_TOKEN:   str = ""
    TWILIO_FROM_NUMBER:  str = ""    # your Twilio phone number, e.g. +15551234567

    # Stripe billing — test-mode keys from dashboard.stripe.com/test/apikeys.
    # Leave blank to run with billing gracefully disabled (same pattern as HA/Twilio).
    STRIPE_SECRET_KEY:      str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET:  str = ""   # from `stripe listen` or the webhook endpoint's settings page
    FRONTEND_URL:           str = "http://localhost:5173"   # Checkout/Portal redirect target

    class Config:
        env_file = ".env"


settings = Settings()

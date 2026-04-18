from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "MYXON Platform"
    environment: str = "development"
    debug: bool = True
    app_base_url: str = "http://localhost:3000"  # Used in invite links sent to customers

    # Database
    database_url: str = "postgresql+asyncpg://myxon:myxon_dev_pass@localhost:5432/myxon"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth / JWT
    secret_key: str = "dev-secret-change-in-prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Agent
    heartbeat_timeout_seconds: int = 60
    heartbeat_interval_seconds: int = 15

    # FRPS
    frps_host: str = "frps"
    frps_bind_port: int = 7000
    frps_dashboard_port: int = 7500
    tunnel_port_range_start: int = 10000
    tunnel_port_range_end: int = 10100
    # Secret shared between frps and our backend webhook — prevents random callers
    # from hitting the auth endpoint. Set a long random string in production.
    frps_plugin_secret: str = "frps-plugin-secret-change-in-prod"

    # Guacamole
    guacd_host: str = "guacd"
    guacd_port: int = 4822

    # Email notifications (SMTP)
    # Leave smtp_host empty to disable email notifications entirely.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@myxon.io"
    smtp_use_tls: bool = True    # STARTTLS on port 587; set False for port 465 (SSL)
    notify_on_alarm: bool = True # Send email on new ALARM or WARNING severity alarms

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

import os
import smtplib
import sqlite3
from email.message import EmailMessage
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import Field


def _load_env_defaults() -> None:
    base_dir = Path(__file__).resolve().parent.parent if (Path(__file__).resolve().parent / "Demo").exists() else Path(__file__).resolve().parent
    env_path = base_dir / ".env"
    if not env_path.exists():
        return

    with env_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_defaults()


class DatabaseMonitorTool(BaseTool):
    name: str = "Database Monitor"
    description: str = "Fetches recent access logs from the database."
    db_path: str = Field(default_factory=lambda: str(
        (Path(__file__).resolve().parent.parent if (Path(__file__).resolve().parent / "Demo").exists() else Path(__file__).resolve().parent) / "Demo" / "app.db"
    ))

    def _run(self) -> str:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT username, role, resource, action, status, timestamp
            FROM access_log
            WHERE timestamp > datetime('now', '-1 hour')
            ORDER BY timestamp DESC
            """
        ).fetchall()
        conn.close()

        if not rows:
            return "No access events in the last hour."

        return "\n".join(
            f"user={r[0]} (role={r[1]}) -> {r[2]} [{r[3]}] status={r[4]} at {r[5]}"
            for r in rows
        )


class SendEmailTool(BaseTool):
    name: str = "Send Email"
    description: str = "Sends a security alert email after a confirmed violation."
    smtp_host: str = Field(default_factory=lambda: os.getenv("MAIL_HOST", os.getenv("SMTP_HOST", "smtp.gmail.com")))
    smtp_port: int = Field(default_factory=lambda: int(os.getenv("MAIL_PORT", os.getenv("SMTP_PORT", "587"))))
    smtp_user: str = Field(default_factory=lambda: os.getenv("MAIL_USERNAME", os.getenv("SMTP_USER", "you@gmail.com")))
    smtp_password: str = Field(default_factory=lambda: os.getenv("MAIL_PASSWORD", os.getenv("SMTP_PASSWORD", "your-app-password")).replace(" ", ""))
    alert_email: str = Field(default_factory=lambda: os.getenv("ALERT_EMAIL", os.getenv("MAIL_USERNAME", "you@gmail.com")))

    def _run(self, subject: str, body: str, context: str) -> str:
        if "VIOLATION_DETECTED" not in context:
            return "NO EMAIL SENT - no violation detected. This is correct behavior."

        if not self.smtp_user or not self.smtp_password:
            return "NO EMAIL SENT - SMTP credentials not configured."

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.alert_email
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.smtp_user, self.smtp_password)
                smtp.send_message(msg)
            return "Alert email sent successfully."
        except Exception as exc:  # pragma: no cover - network-dependent path
            return f"EMAIL SEND FAILED: {exc}"
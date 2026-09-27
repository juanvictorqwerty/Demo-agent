import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import Agent, Crew, LLM, Process, Task

try:
    from agent.tools import DatabaseMonitorTool, SendEmailTool
except ModuleNotFoundError:
    from tools import DatabaseMonitorTool, SendEmailTool

project_root = Path(__file__).resolve().parent.parent if (Path(__file__).resolve().parent / "Demo").exists() else Path(__file__).resolve().parent
load_dotenv(dotenv_path=project_root / ".env", override=False)

DB_PATH = project_root / "Demo" / "app.db"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
if openrouter_key:
    os.environ.setdefault("OPENAI_API_KEY", openrouter_key)
    os.environ.setdefault("OPENAI_BASE_URL", OPENROUTER_BASE_URL)
    os.environ.setdefault("OPENAI_API_BASE", OPENROUTER_BASE_URL)

llm = LLM(
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", os.getenv("OPENAI_BASE_URL", OPENROUTER_BASE_URL)),
    max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "512")),
    temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.1")),
)

monitor = Agent(
    role="Database Monitor",
    goal="Retrieve and summarize the latest database access logs.",
    backstory="You watch access patterns and report them factually.",
    tools=[DatabaseMonitorTool(db_path=str(DB_PATH))],
    llm=llm,
    verbose=True,
)

analyst = Agent(
    role="Security Analyst",
    goal="Flag any access by non-admin users to admin-only resources.",
    backstory="You know exactly which resources are restricted to admins.",
    llm=llm,
    verbose=True,
)

dispatcher = Agent(
    role="Alert Dispatcher",
    goal="Send a security alert email — but ONLY when a violation is confirmed.",
    backstory="You never send emails without a confirmed VIOLATION_DETECTED flag.",
    tools=[
        SendEmailTool(
            smtp_host=os.getenv("MAIL_HOST", os.getenv("SMTP_HOST", "smtp.gmail.com")),
            smtp_port=int(os.getenv("MAIL_PORT", os.getenv("SMTP_PORT", "465"))),
            smtp_user=os.getenv("MAIL_USERNAME", os.getenv("SMTP_USER", "you@gmail.com")),
            smtp_password=os.getenv("MAIL_PASSWORD", os.getenv("SMTP_PASSWORD", "your-app-password")),
            alert_email=os.getenv("ALERT_EMAIL", os.getenv("MAIL_USERNAME", "you@gmail.com")),
        )
    ],
    llm=llm,
    verbose=True,
)

task_monitor = Task(
    description="Pull the last hour of access logs and list each event.",
    agent=monitor,
    expected_output="A plain list of access events with user, role, resource, action, timestamp.",
)

task_analyze = Task(
    description=(
        "Review the logs. Admin-only resources start with '/admin/'. "
        "If any user with role != 'admin' touched one — whether status 403 (attempt) "
        "or 200 (actual access) — output 'VIOLATION_DETECTED' followed by details. "
        "status 200 by a non-admin is CRITICAL, status 403 is a WARNING. "
        "Otherwise output 'ALL_CLEAR'."
    ),
    agent=analyst,
    expected_output="VIOLATION_DETECTED + details, or ALL_CLEAR.",
    context=[task_monitor],
)

task_alert = Task(
    description=(
        "Check the analyst's verdict. If it contains VIOLATION_DETECTED, send an alert "
        "email with subject 'Security Alert: unauthorized access' and a body summarizing "
        "the offending events. Pass the analyst output as the 'context' argument to the email tool."
    ),
    agent=dispatcher,
    expected_output="Confirmation email was sent, or a statement that no email was sent.",
    context=[task_analyze],
)

crew = Crew(
    agents=[monitor, analyst, dispatcher],
    tasks=[task_monitor, task_analyze, task_alert],
    process=Process.sequential,
)

result = crew.kickoff()
print(result)
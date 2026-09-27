# Demo Agent

This project demonstrates a realistic security-monitoring pipeline:

- an Express app writes audit events to a shared SQLite database
- a CrewAI agent reads those logs and looks for unauthorized admin access
- the analyst flags suspicious activity
- a dispatcher can send an alert email when a violation is detected

## Project structure

```text
Demo agent/
├── Demo/
│   ├── app.db
│   ├── package.json
│   ├── pnpm-lock.yaml
│   └── server.js
├── agent/
│   ├── main.py
│   └── tools.py
├── .env
├── .gitignore
├── pyproject.toml
├── README.md
└── uv.lock
```

## Prerequisites

- Node.js and pnpm
- Python 3.10+
- A valid OpenRouter API key in `.env`
- A valid Gmail app password in `.env` if email alerts are enabled

## Environment variables

Create a `.env` file in the project root with values like:

```env
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_MAX_TOKENS=512
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_16_char_app_password
ALERT_EMAIL=your_email@gmail.com
```

## Install dependencies

### Python

```bash
cd "/home/linux/Desktop/Demo agent"
uv sync
```

If you need to add packages manually:

```bash
uv add crewai python-dotenv
```

### Node

```bash
cd "/home/linux/Desktop/Demo agent/Demo"
pnpm install
```

## How to use it

Use three terminals:

### Terminal 1: start the app

```bash
cd "/home/linux/Desktop/Demo agent/Demo"
pnpm install
pnpm start
```

This starts the Express app and creates the SQLite database at `Demo/app.db`.

### Terminal 2: generate fake access events

```bash
curl -i -H "Authorization: Bearer token-alice" http://localhost:3000/admin/users
curl -i -H "Authorization: Bearer token-bob" http://localhost:3000/admin/billing
curl -i -H "Authorization: Bearer token-carol" http://localhost:3000/public/profile
```

What this simulates:

- `alice` is admin and can access `/admin/users`
- `bob` is a normal user and gets blocked on `/admin/billing`
- `carol` is a normal user and accesses a public route

The blocked attempt is still written to the access log with status `403`, which the agent should flag.

### Terminal 3: run the agent

```bash
cd "/home/linux/Desktop/Demo agent"
python agent/main.py
```

The agent will:

1. read the last hour of access logs
2. identify unauthorized admin access
3. output `VIOLATION_DETECTED` when it finds one
4. try to send the alert email if the email config is valid

## If the database is missing

If the Python agent says the database file cannot be opened, the Express app is probably not running yet. Start the app in Terminal 1 and wait for it to initialize before running the agent.

## Expected behavior

The agent should:

- read the access log from SQLite
- detect bob’s denied attempt to `/admin/billing`
- flag it as `VIOLATION_DETECTED`
- send an alert email when the SMTP configuration is valid

## Notes

- The Node server creates and updates `Demo/app.db`.
- The database uses WAL mode so the Python agent can read the shared file while the Node app is writing to it.
- Gmail SMTP requires an app password, not your normal account password.

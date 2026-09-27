const express = require('express');
const Database = require('better-sqlite3');

const app = express();
const port = process.env.PORT || 3000;

// ---------- DB (shared with your Python agent) ----------
const db = new Database('app.db');
db.pragma('journal_mode = WAL');  // lets Python read while Node writes
db.exec(`
  CREATE TABLE IF NOT EXISTS access_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER,
    username  TEXT,
    role      TEXT,
    resource  TEXT,
    action    TEXT,
    status    INTEGER,
    ip        TEXT,
    timestamp TEXT DEFAULT (datetime('now'))
  )
`);

const logAccess = db.prepare(`
  INSERT INTO access_log (user_id, username, role, resource, action, status, ip)
  VALUES (@user_id, @username, @role, @resource, @action, @status, @ip)
`);

// ---------- Mock auth (bearer token -> user) ----------
const USERS = {
  'token-alice': { user_id: 1, username: 'alice', role: 'admin' },
  'token-bob':   { user_id: 2, username: 'bob',   role: 'user'  },
  'token-carol': { user_id: 3, username: 'carol', role: 'user'  },
};

function auth(req, res, next) {
  const token = (req.headers.authorization || '').replace('Bearer ', '');
  const user = USERS[token];
  if (!user) return res.status(401).json({ error: 'unauthorized' });
  req.user = user;
  next();
}

function requireAdmin(req, res, next) {
  if (req.user.role !== 'admin') {
    // Log the DENIED attempt — this is exactly what the agent should catch
    logAccess.run({ ...req.user, resource: req.path, action: req.method, status: 403, ip: req.ip });
    return res.status(403).json({ error: 'forbidden: admin only' });
  }
  next();
}

// ---------- Audit middleware: log every successful request ----------
app.use((req, res, next) => {
  res.on('finish', () => {
    if (req.user && res.statusCode < 400) {
      logAccess.run({ ...req.user, resource: req.path, action: req.method,
                      status: res.statusCode, ip: req.ip });
    }
  });
  next();
});

app.use(express.json());

// ---------- Routes ----------
app.get('/', (req, res) => {
  res.json({ message: 'Hello from demo-node-app' });
});

app.get('/public/profile', auth, (req, res) => {
  res.json({ profile: req.user.username });
});

app.get('/admin/users', auth, requireAdmin, (req, res) => {
  res.json({ users: Object.values(USERS).map(u => u.username) });
});

app.get('/admin/billing', auth, requireAdmin, (req, res) => {
  res.json({ billing: 'some billing data' });
});

app.listen(port, () => console.log(`Server listening on port ${port}`));
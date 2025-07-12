// server.js - Production-ready Express server for radio traffic system
// Includes: JWT authentication, admin user management, secure file uploads, PostgreSQL integration

const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const cookieParser = require("cookie-parser");
const { Pool } = require("pg");

// Setup
const app = express();
const PORT = process.env.PORT || 3010;
const JWT_SECRET = process.env.JWT_SECRET || "supersecret";

// PostgreSQL connection pool
const db = new Pool({
  connectionString: process.env.DATABASE_URL || "postgres://user:pass@localhost:5432/trafficdb"
});

// Middleware
app.use(express.static("public")); // serve frontend build
app.use(express.json());           // parse JSON request bodies
app.use(cookieParser());           // parse cookies for JWT auth

// Create upload directory if missing
const uploadDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);

// Configure multer for file upload handling
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => cb(null, Date.now() + "-" + file.originalname)
});
const upload = multer({ storage });

// Middleware: Auth check
function requireAuth(req, res, next) {
  const token = req.cookies.token;
  if (!token) return res.status(401).json({ error: "Unauthorized" });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    return res.status(401).json({ error: "Invalid token" });
  }
}

// Middleware: Admin role check
function requireAdmin(req, res, next) {
  requireAuth(req, res, () => {
    if (req.user.role !== "admin") return res.status(403).json({ error: "Forbidden" });
    next();
  });
}

// ------------------------
// API ROUTES
// ------------------------

// Register new user (admin-only or for seed init)
app.post("/api/register", async (req, res) => {
  const { email, password, role = "user" } = req.body;
  const hash = await bcrypt.hash(password, 10);
  try {
    const result = await db.query(
      "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, $3) RETURNING id, email, role",
      [email, hash, role]
    );
    res.json(result.rows[0]);
  } catch (err) {
    res.status(400).json({ error: "Registration failed", details: err.detail });
  }
});

// Login user (sets httpOnly cookie with JWT)
app.post("/api/login", async (req, res) => {
  const { email, password } = req.body;
  const result = await db.query("SELECT * FROM users WHERE email=$1", [email]);
  const user = result.rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash)))
    return res.status(401).json({ error: "Invalid credentials" });

  const token = jwt.sign({ id: user.id, email: user.email, role: user.role }, JWT_SECRET, { expiresIn: "1d" });
  res.cookie("token", token, { httpOnly: true }).json({ message: "Logged in" });
});

// Logout user (clears cookie)
app.post("/api/logout", (req, res) => {
  res.clearCookie("token").json({ message: "Logged out" });
});

// Get all users (admin only)
app.get("/api/users", requireAdmin, async (req, res) => {
  const result = await db.query("SELECT id, email, role FROM users ORDER BY id");
  res.json(result.rows);
});

// Update user email/role (admin only)
app.put("/api/users/:id", requireAdmin, async (req, res) => {
  const { email, role } = req.body;
  await db.query("UPDATE users SET email=$1, role=$2 WHERE id=$3", [email, role, req.params.id]);
  res.json({ message: "User updated" });
});

// Delete user (admin only)
app.delete("/api/users/:id", requireAdmin, async (req, res) => {
  await db.query("DELETE FROM users WHERE id=$1", [req.params.id]);
  res.json({ message: "User deleted" });
});

// Upload an advert audio file
app.post("/api/upload", requireAuth, upload.single("file"), (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });
  res.json({ filename: req.file.filename, path: `/uploads/${req.file.filename}` });
});

// Health check
app.get("/api/ping", (req, res) => res.send("Server is running!"));

// Start server
app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`);
});

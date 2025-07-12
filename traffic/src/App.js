// src/App.js - Main app router for authenticated traffic scheduling system

import React, { useState, useEffect } from "react";
import Login from "./components/Login";
import AdminUsers from "./components/AdminUsers";
import TrafficScheduler from "./components/TrafficScheduler";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  // On initial load, check login status and user role
  useEffect(() => {
    fetch("/api/users", { credentials: "include" })
      .then(res => {
        if (res.ok) {
          setIsLoggedIn(true);
          setIsAdmin(true);
        } else {
          // If 401/403 returned, not an admin
          fetch("/api/ping", { credentials: "include" })
            .then(pingRes => setIsLoggedIn(pingRes.ok));
        }
      });
  }, []);

  // Not logged in: show login page
  if (!isLoggedIn) {
    return <Login onLogin={() => {
      setIsLoggedIn(true);
      // Re-check admin access
      fetch("/api/users", { credentials: "include" })
        .then(res => setIsAdmin(res.ok));
    }} />;
  }

  // Logged in user: route by role
  return isAdmin ? <AdminUsers /> : <TrafficScheduler />;
}

export default App;

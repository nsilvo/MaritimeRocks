function App() {
  const [isLoggedIn, setIsLoggedIn] = React.useState(() => localStorage.getItem("isLoggedIn") === "true");
  const [userRole, setUserRole] = React.useState(() => localStorage.getItem("userRole"));
  const [view, setView] = React.useState("dashboard");
  const [darkMode, setDarkMode] = React.useState(() => localStorage.getItem("darkMode") === "true");

  React.useEffect(() => {
    localStorage.setItem("isLoggedIn", isLoggedIn);
    localStorage.setItem("userRole", userRole);
    localStorage.setItem("darkMode", darkMode);
  }, [isLoggedIn, userRole, darkMode]);

  const themeStyles = {
    backgroundColor: darkMode ? "#1e1e1e" : "#f8f8f8",
    color: darkMode ? "#eee" : "#111",
    minHeight: "100vh",
  };

  if (!isLoggedIn)
    return <Login onLogin={(role) => { setIsLoggedIn(true); setUserRole(role); }} />;

  let content;
  switch (view) {
    case "users":
      content = userRole === "admin" ? <AdminUsers /> : <p style={{ padding: 20 }}>Access denied: Admins only</p>;
      break;
    case "upload": content = <TrafficScheduler />; break;
    case "campaigns": content = <CampaignManager />; break;
    case "planner": content = <SchedulePlanner />; break;
    default:
      content = (
        <div style={{ padding: 20 }}>
          <h2>📊 Dashboard</h2>
          <p>Welcome to the Radio Traffic Scheduler</p>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <div style={{ background: "#eef", padding: 20, borderRadius: 10, flex: 1 }}>
              <h3>✔️ Users</h3>
              <p>Manage user access and roles (admin only)</p>
            </div>
            <div style={{ background: "#efe", padding: 20, borderRadius: 10, flex: 1 }}>
              <h3>📂 Upload</h3>
              <p>Upload audio files and schedule documents</p>
            </div>
            <div style={{ background: "#fee", padding: 20, borderRadius: 10, flex: 1 }}>
              <h3>🎯 Campaigns</h3>
              <p>Create and manage advertisement campaigns</p>
            </div>
            <div style={{ background: "#eef", padding: 20, borderRadius: 10, flex: 1 }}>
              <h3>📅 Planner</h3>
              <p>Plan and export daily advert schedules</p>
            </div>
          </div>
        </div>
      );
  }

  return (
    <div style={themeStyles}>
      <nav style={{ background: darkMode ? "#111" : "#2b2b2b", color: "white", padding: 10, display: "flex", justifyContent: "space-between" }}>
        <div>
          <button onClick={() => setView("dashboard")}>🏠 Dashboard</button>
          {userRole === "admin" && <button onClick={() => setView("users")}>👤 Users</button>}
          <button onClick={() => setView("upload")}>📤 Upload</button>
          <button onClick={() => setView("campaigns")}>📢 Campaigns</button>
          <button onClick={() => setView("planner")}>🗓️ Planner</button>
        </div>
        <div>
          <label style={{ marginRight: 10 }}>
            <input
              type="checkbox"
              checked={darkMode}
              onChange={() => setDarkMode(!darkMode)}
            /> {darkMode ? "🌙" : "☀️"}
          </label>
          <span style={{ marginRight: 10 }}>👋 {userRole}</span>
          <button onClick={() => {
            setIsLoggedIn(false);
            setUserRole(null);
            localStorage.clear();
          }}>🚪 Logout</button>
        </div>
      </nav>
      {content}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

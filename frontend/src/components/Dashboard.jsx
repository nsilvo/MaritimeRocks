import { useEffect, useState } from "react";
import { fetchDashboard } from "../api";

function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchDashboard().then(({ data }) => setStats(data));
  }, []);

  if (!stats) return <div>Loading dashboard...</div>;

  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      <div className="card shadow p-4">
        <h2 className="text-xl">Total Clips</h2>
        <p className="text-2xl">{stats.total_clips}</p>
      </div>
      <div className="card shadow p-4">
        <h2 className="text-xl">Blocked Clips</h2>
        <p className="text-2xl">{stats.blocked_clips}</p>
      </div>
      <div className="card shadow p-4 col-span-2">
        <h2 className="text-xl">Category Breakdown</h2>
        <ul>
          {Object.entries(stats.clips_per_category).map(([cat, count]) => (
            <li key={cat}>
              {cat}: {count}
            </li>
          ))}
        </ul>
      </div>
      <div className="card shadow p-4 col-span-2">
        <h2 className="text-xl">Recently Played Clips</h2>
        <ul>
          {stats.recent_played_clips.map((clip, idx) => (
            <li key={idx}>
              {clip.artist || "Unknown Artist"} - {clip.title || "Unknown Title"}
              <br />
              <small className="text-gray-500">{clip.started}</small>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default Dashboard;

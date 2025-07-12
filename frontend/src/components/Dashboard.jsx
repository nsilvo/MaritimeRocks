import { useEffect, useState, useRef } from "react";
import { fetchDashboard } from "../api";

const DEBUG = true;

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [nowPlaying, setNowPlaying] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const requestRef = useRef();

  useEffect(() => {
    const loadDashboard = async () => {
      const { data } = await fetchDashboard();
      if (DEBUG) console.log("Fetched Dashboard Data:", data);
      setStats(data);
      const current = data.recent_played_clips?.[0];
      if (current) {
        if (DEBUG) console.log("Now Playing:", current);
        setNowPlaying(current);
      }
    };

    loadDashboard();
    const refreshInterval = setInterval(loadDashboard, 10000);
    return () => clearInterval(refreshInterval);
  }, []);

  useEffect(() => {
    const updateElapsed = () => {
      if (!nowPlaying) return;
      const startedAt = new Date(nowPlaying.started + 'Z').getTime();
      const now = Date.now();
      const newElapsed = (now - startedAt) / 1000;
      setElapsed(newElapsed);
      requestRef.current = requestAnimationFrame(updateElapsed);
    };

    if (nowPlaying) {
      requestRef.current = requestAnimationFrame(updateElapsed);
    }

    return () => cancelAnimationFrame(requestRef.current);
  }, [nowPlaying]);

  if (!stats) return <div>Loading dashboard...</div>;

  const durationSeconds = nowPlaying?.duration || 0;
  const progress = durationSeconds > 0 ? Math.min((elapsed / durationSeconds) * 100, 100) : 0;
  const isPlaying = elapsed < durationSeconds;
  const isEnding = durationSeconds - elapsed <= 10;

  if (DEBUG) {
    console.log("Duration (s):", durationSeconds);
    console.log("Elapsed:", elapsed);
    console.log("Progress:", progress);
  }

  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      {nowPlaying && isPlaying && (
        <div className="card shadow p-4 col-span-2 bg-neutral text-neutral-content">
          <h2 className="text-xl mb-2">Now Playing</h2>
          <p className="text-lg">
            {nowPlaying.artist || "Unknown Artist"} – {nowPlaying.title || "Unknown Title"}
          </p>
          <div className="relative w-full h-6 mt-2 rounded border border-gray-500 bg-base-300 overflow-hidden">
            {/* Grey overlay for final 10 seconds */}
            <div
              className="absolute top-0 right-0 h-full bg-gray-700 opacity-30 pointer-events-none"
              style={{ width: `${Math.min((30 / durationSeconds) * 100, 100)}%` }}
            ></div>
            {/* Playback progress bar */}
            <div
              className={`absolute top-0 left-0 h-full origin-left pointer-events-none ${isEnding ? "bg-red-500 animate-[flash_0.5s_ease-in-out_infinite]" : "bg-pink-500"}`}
              style={{ width: `${progress}%`, transition: 'width 0.5s' }}
            ></div>
            {isEnding && (
              <div className="absolute top-0 left-0 w-full h-full flex items-center justify-center text-sm font-bold text-white animate-[flash_0.5s_ease-in-out_infinite]">
                Ending Soon…
              </div>
            )}
          </div>
          <div className="text-sm mt-1">
            {Math.min(elapsed, durationSeconds).toFixed(1)}s / {durationSeconds.toFixed(1)}s
          </div>
        </div>
      )}

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

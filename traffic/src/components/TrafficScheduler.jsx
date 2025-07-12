// src/components/TrafficScheduler.jsx - UI to upload ads and assign them to schedule
import React, { useState, useEffect } from "react";

const mockCategories = ["Printing", "Retail", "Finance", "Food"];
const defaultSchedule = [
  { time: "08:00", ads: [] },
  { time: "12:00", ads: [] },
  { time: "16:00", ads: [] },
];

export default function TrafficScheduler() {
  const [ads, setAds] = useState([]);
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [newAd, setNewAd] = useState({ name: "", category: "Printing", file: null });

  // Upload file and save metadata
  const handleFileUpload = async () => {
    if (!newAd.name || !newAd.file) return alert("Ad name and file required");
    const formData = new FormData();
    formData.append("file", newAd.file);

    try {
      const uploadRes = await fetch("/api/upload", {
        method: "POST",
        body: formData,
        credentials: "include"
      });
      const result = await uploadRes.json();

      if (result.filename) {
        const newEntry = { ...newAd, file: result.filename };
        setAds([...ads, newEntry]);
        setNewAd({ name: "", category: "Printing", file: null });
      }
    } catch (error) {
      console.error("Upload error:", error);
    }
  };

  // Assign an ad to a schedule time slot
  const assignAdToSlot = (time) => {
    const slot = schedule.find((s) => s.time === time);
    if (!slot) return;
    const lastCategory = slot.ads.length ? slot.ads[slot.ads.length - 1].category : null;
    const nextAd = ads.find((ad) => ad.category !== lastCategory);
    if (nextAd) {
      slot.ads.push(nextAd);
      setSchedule([...schedule]);
    }
  };

  // Export schedule as JSON
  const handleExport = () => {
    const output = schedule.map((slot) => ({
      time: slot.time,
      ads: slot.ads.map((a) => a.name).join(", ")
    }));
    const blob = new Blob([JSON.stringify(output, null, 2)], {
      type: "application/json"
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "schedule.json";
    link.click();
  };

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">📻 Traffic Scheduler</h1>

      {/* Upload Section */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-2">Upload New Advert</h2>
        <input
          type="text"
          placeholder="Advert Name"
          value={newAd.name}
          onChange={(e) => setNewAd({ ...newAd, name: e.target.value })}
          className="block border p-2 mb-2 w-full"
        />
        <select
          value={newAd.category}
          onChange={(e) => setNewAd({ ...newAd, category: e.target.value })}
          className="block border p-2 mb-2 w-full"
        >
          {mockCategories.map((cat) => (
            <option key={cat}>{cat}</option>
          ))}
        </select>
        <input
          type="file"
          onChange={(e) => setNewAd({ ...newAd, file: e.target.files[0] })}
          className="block mb-2"
        />
        <button onClick={handleFileUpload} className="bg-blue-600 text-white px-4 py-2 rounded">
          Upload
        </button>
      </div>

      {/* Schedule Section */}
      <div>
        <h2 className="text-xl font-semibold mb-2">Schedule</h2>
        <table className="w-full border">
          <thead>
            <tr>
              <th className="border p-2">Time</th>
              <th className="border p-2">Scheduled Ads</th>
              <th className="border p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {schedule.map((slot) => (
              <tr key={slot.time}>
                <td className="border p-2">{slot.time}</td>
                <td className="border p-2">{slot.ads.map((ad) => ad.name).join(", ")}</td>
                <td className="border p-2">
                  <button
                    onClick={() => assignAdToSlot(slot.time)}
                    className="bg-green-500 text-white px-2 py-1 rounded"
                  >
                    Add Ad
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button onClick={handleExport} className="mt-4 bg-black text-white px-4 py-2 rounded">
          Export Schedule
        </button>
      </div>
    </div>
  );
}

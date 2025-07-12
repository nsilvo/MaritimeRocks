function SchedulePlanner() {
  const [stations, setStations] = React.useState([]);
  const [selectedStation, setSelectedStation] = React.useState(null);
  const [day, setDay] = React.useState(new Date().toISOString().substring(0, 10));
  const [slots, setSlots] = React.useState(Array(24).fill(""));
  const [conflicts, setConflicts] = React.useState([]);

  React.useEffect(() => {
    fetch("/api/stations", { credentials: "include" })
      .then(res => res.json())
      .then(data => {
        setStations(data);
        if (data.length) setSelectedStation(data[0].id);
      });
  }, []);

  function handleSlotChange(index, value) {
    const updated = [...slots];
    updated[index] = value;
    setSlots(updated);
  }

  async function validateAndSave() {
    const res = await fetch("/api/schedule/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ stationId: selectedStation, day, slots })
    });
    const result = await res.json();
    if (result.ok) {
      await fetch("/api/schedule/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ stationId: selectedStation, day, slots })
      });
      alert("Schedule saved.");
    } else {
      setConflicts(result.conflicts);
    }
  }

  function copyFromYesterday() {
    const d = new Date(day);
    d.setDate(d.getDate() - 1);
    fetch(`/api/schedule?stationId=${selectedStation}&day=${d.toISOString().substring(0, 10)}`, { credentials: "include" })
      .then(res => res.json())
      .then(data => {
        if (data.slots) setSlots(data.slots);
      });
  }

  function exportPlayoutONE() {
    const content = slots.map((ad, hour) => `${hour}:00 - ${ad}`).join("\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `schedule_${selectedStation}_${day}.txt`;
    a.click();
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Schedule Planner</h2>
      <label>
        Station:
        <select value={selectedStation || ""} onChange={e => setSelectedStation(e.target.value)}>
          {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </label>
      <label style={{ marginLeft: 20 }}>
        Day: <input type="date" value={day} onChange={e => setDay(e.target.value)} />
      </label>
      <button onClick={copyFromYesterday} style={{ marginLeft: 20 }}>Copy from yesterday</button>
      <button onClick={exportPlayoutONE} style={{ marginLeft: 10 }}>Export (PlayoutONE)</button>

      <table style={{ marginTop: 20 }}>
        <thead><tr><th>Hour</th><th>Ad</th></tr></thead>
        <tbody>
          {slots.map((slot, i) => (
            <tr key={i} style={{ background: conflicts.includes(i) ? "#fdd" : "" }}>
              <td>{i}:00</td>
              <td><input value={slot} onChange={e => handleSlotChange(i, e.target.value)} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <button onClick={validateAndSave}>Save</button>

      {conflicts.length > 0 && (
        <p style={{ color: "red" }}>
          ⚠️ Conflict at: {conflicts.join(", ")} (duplicate ad types)
        </p>
      )}
    </div>
  );
}

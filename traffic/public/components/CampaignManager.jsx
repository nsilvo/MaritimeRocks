function CampaignManager() {
  const [campaigns, setCampaigns] = React.useState([]);
  const [form, setForm] = React.useState({ name: "", client: "", start: "", end: "" });
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    fetch("/api/campaigns", { credentials: "include" })
      .then(res => res.json())
      .then(setCampaigns);
  }, []);

  async function createCampaign(e) {
    e.preventDefault();
    const res = await fetch("/api/campaigns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(form)
    });
    if (res.ok) {
      const newCampaign = await res.json();
      setCampaigns([...campaigns, newCampaign]);
      setForm({ name: "", client: "", start: "", end: "" });
      setMessage("Campaign created");
    } else {
      setMessage("Failed to create campaign");
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Campaign Management</h2>
      <form onSubmit={createCampaign}>
        <input placeholder="Campaign Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="Client" value={form.client} onChange={e => setForm({ ...form, client: e.target.value })} required />
        <input type="date" value={form.start} onChange={e => setForm({ ...form, start: e.target.value })} required />
        <input type="date" value={form.end} onChange={e => setForm({ ...form, end: e.target.value })} required />
        <button type="submit">Create Campaign</button>
      </form>
      {message && <p>{message}</p>}

      <ul>
        {campaigns.map(c => (
          <li key={c.id}>{c.name} ({c.client}) [{c.start} → {c.end}]</li>
        ))}
      </ul>
    </div>
  );
}
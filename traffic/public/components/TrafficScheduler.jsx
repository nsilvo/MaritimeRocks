function TrafficScheduler() {
  const [file, setFile] = React.useState(null);
  const [msg, setMsg] = React.useState("");

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
      credentials: "include"
    });
    if (res.ok) {
      const result = await res.json();
      setMsg(`Uploaded: ${result.filename}`);
    } else {
      setMsg("Upload failed.");
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Upload Schedule or Audio</h2>
      <form onSubmit={handleUpload}>
        <input type="file" onChange={e => setFile(e.target.files[0])} required />
        <button type="submit">Upload</button>
      </form>
      {msg && <p>{msg}</p>}
    </div>
  );
}

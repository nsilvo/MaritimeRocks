function AdminUsers() {
  const [users, setUsers] = React.useState([]);

  React.useEffect(() => {
    fetch("/api/users", { credentials: "include" })
      .then(res => res.json())
      .then(setUsers);
  }, []);

  async function deleteUser(id) {
    if (!confirm("Delete this user?")) return;
    await fetch(`/api/users/${id}`, {
      method: "DELETE",
      credentials: "include"
    });
    setUsers(users.filter(u => u.id !== id));
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Admin: User Management</h2>
      <table border="1" cellPadding="5">
        <thead>
          <tr><th>ID</th><th>Email</th><th>Role</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {users.map(user => (
            <tr key={user.id}>
              <td>{user.id}</td>
              <td>{user.email}</td>
              <td>{user.role}</td>
              <td>
                <button onClick={() => deleteUser(user.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
// src/components/AdminUsers.jsx - Admin panel for managing users
import React, { useEffect, useState } from "react";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);

  // Load all users
  const fetchUsers = async () => {
    const res = await fetch("/api/users", { credentials: "include" });
    const data = await res.json();
    setUsers(data);
  };

  // Update a user's email/role
  const updateUser = async (id, email, role) => {
    await fetch(`/api/users/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, role })
    });
    fetchUsers();
  };

  // Delete a user
  const deleteUser = async (id) => {
    if (window.confirm("Are you sure you want to delete this user?")) {
      await fetch(`/api/users/${id}`, {
        method: "DELETE",
        credentials: "include"
      });
      fetchUsers();
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">User Management</h2>
      <table className="w-full border">
        <thead>
          <tr>
            <th className="border p-2">Email</th>
            <th className="border p-2">Role</th>
            <th className="border p-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td className="border p-2">
                <input
                  value={user.email}
                  onChange={(e) =>
                    setUsers(users.map(u =>
                      u.id === user.id ? { ...u, email: e.target.value } : u
                    ))
                  }
                  className="w-full border p-1"
                />
              </td>
              <td className="border p-2">
                <select
                  value={user.role}
                  onChange={(e) =>
                    setUsers(users.map(u =>
                      u.id === user.id ? { ...u, role: e.target.value } : u
                    ))
                  }
                  className="w-full border p-1"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td className="border p-2 space-x-2">
                <button
                  onClick={() => updateUser(user.id, user.email, user.role)}
                  className="bg-green-600 text-white px-2 py-1 rounded"
                >
                  Save
                </button>
                <button
                  onClick={() => deleteUser(user.id)}
                  className="bg-red-600 text-white px-2 py-1 rounded"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

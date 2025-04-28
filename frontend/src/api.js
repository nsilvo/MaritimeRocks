import axios from "axios";

const API = axios.create({
  baseURL: "http://192.168.1.250:8000", // Adjust if needed
});

// Fetch all media
export const fetchMedia = (category) =>
  API.get("/media", { params: category ? { category } : {} });

// Update a media item
export const updateMedia = (id, data) =>
  API.patch(`/media/${id}`, data);

// Delete a media item
export const deleteMedia = (id) =>
  API.delete(`/media/${id}`);

// Fetch dashboard stats
export const fetchDashboard = () =>
  API.get("/dashboard");

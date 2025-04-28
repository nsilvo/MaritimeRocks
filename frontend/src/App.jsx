import MediaTable from "./components/MediaTable";
import Dashboard from "./components/Dashboard";

function App() {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-4">Maritime Rocks - Media Manager</h1>
      <Dashboard />
      <hr className="my-6" />
      <MediaTable />
    </div>
  );
}

export default App;

import { useEffect, useState, useMemo } from "react";
import { useReactTable, getCoreRowModel, flexRender } from "@tanstack/react-table";
import { fetchMedia, updateMedia, deleteMedia } from "../api";

import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import "jspdf-autotable";

function MediaTable() {
  const [mediaList, setMediaList] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [saveMessage, setSaveMessage] = useState("");

  const loadMedia = async () => {
    const { data } = await fetchMedia(categoryFilter);
    setMediaList(data);
  };
  const exportToExcel = () => {
    const worksheet = XLSX.utils.json_to_sheet(mediaList);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Media List");
    XLSX.writeFile(workbook, "MaritimeRocks_Media.xlsx");
  };
  
  const exportToPDF = () => {
    const doc = new jsPDF();
    const tableColumn = ["ID", "Artist", "Title", "Path", "Year", "Category"];
    const tableRows = [];
  
    mediaList.forEach((media) => {
      tableRows.push([
        media.id,
        media.artist || "",
        media.title || "",
        media.path || "",
        media.release_year || "",
        media.category || ""
      ]);
    });
  
    doc.autoTable({
      head: [tableColumn],
      body: tableRows,
    });
    doc.save("MaritimeRocks_Media.pdf");
  };
  useEffect(() => {
    loadMedia();
  }, [categoryFilter]);

  const handleUpdate = async (id, field, value) => {
    try {
      if (field === "release_year") {
        if (value === "" || value === null) {
          value = null;
        } else {
          const parsed = parseInt(value);
          if (isNaN(parsed)) {
            alert("Release year must be a number.");
            return;
          }
          value = parsed;
        }
      }
      if (field === "blocked") {
        value = value ? 1 : 0;
      }

      await updateMedia(id, { [field]: value });
      await loadMedia();
      setSaveMessage("Saved successfully.");
      setTimeout(() => setSaveMessage(""), 2000);
    } catch (err) {
      console.error(err);
      alert("Failed to update media entry!");
    }
  };

  const handleDelete = async (id) => {
    if (confirm("Are you sure you want to delete this clip?")) {
      await deleteMedia(id);
      await loadMedia();
    }
  };

  const filteredList = mediaList.filter(
    (item) =>
      item.artist?.toLowerCase().includes(search.toLowerCase()) ||
      item.title?.toLowerCase().includes(search.toLowerCase())
  );

  const columns = useMemo(() => [
    {
      header: "Path",
      accessorKey: "path",
      cell: ({ row }) => (
        <div className="whitespace-normal break-words">{row.original.path}</div>
      ),
    },
    {
      header: "Artist",
      accessorKey: "artist",
      cell: ({ row }) => (
        <input
          className="input input-xs"
          defaultValue={row.original.artist}
          onBlur={(e) => handleUpdate(row.original.id, "artist", e.target.value)}
        />
      ),
    },
    {
      header: "Title",
      accessorKey: "title",
      cell: ({ row }) => (
        <input
          className="input input-xs"
          defaultValue={row.original.title}
          onBlur={(e) => handleUpdate(row.original.id, "title", e.target.value)}
        />
      ),
    },
    {
      header: "Year",
      accessorKey: "release_year",
      cell: ({ row }) => (
        <input
          type="number"
          className="input input-xs"
          defaultValue={row.original.release_year}
          onBlur={(e) => handleUpdate(row.original.id, "release_year", e.target.value)}
        />
      ),
    },
    {
      header: "Category",
      accessorKey: "category",
      cell: ({ row }) => (
        <input
          className="input input-xs"
          defaultValue={row.original.category}
          onBlur={(e) => handleUpdate(row.original.id, "category", e.target.value)}
        />
      ),
    },
    {
      header: "Blocked",
      accessorKey: "blocked",
      cell: ({ row }) => (
        <button
          className={`btn btn-xs ${row.original.blocked ? "btn-error" : "btn-success"}`}
          onClick={() => handleUpdate(row.original.id, "blocked", row.original.blocked ? 0 : 1)}
        >
          {row.original.blocked ? "Blocked" : "Allowed"}
        </button>
      ),
    },
    {
      header: "Actions",
      cell: ({ row }) => (
        <button
          className="btn btn-xs btn-outline btn-error"
          onClick={() => handleDelete(row.original.id)}
        >
          Delete
        </button>
      ),
    },
  ], []);

  const table = useReactTable({
    data: filteredList,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="p-4">
      <div className="flex items-center gap-4 mb-4">
        <input
          type="text"
          placeholder="Search artist or title..."
          className="input input-bordered w-full"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="select select-bordered"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">All Categories</option>
          <option value="Rock">Rock</option>
          <option value="Advert">Advert</option>
          <option value="Promo">Promo</option>
        </select>

        <button className="btn btn-primary" onClick={exportToExcel} > Export Excel </button>
  <button className="btn btn-secondary" onClick={exportToPDF} > Export PDF </button>
      </div>

      {saveMessage && (
        <div className="alert alert-success mb-4">
          {saveMessage}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="table table-zebra w-full">
          <thead>
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th key={header.id}>
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr key={row.id}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default MediaTable;

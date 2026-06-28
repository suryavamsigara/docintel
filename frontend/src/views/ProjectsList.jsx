import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderGit2, Plus, Loader2 } from 'lucide-react';

export default function ProjectsList() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const navigate = useNavigate();

  const fetchProjects = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/projects');
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      console.error("Failed to fetch projects", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;

    try {
      const formData = new FormData();
      formData.append('name', newProjectName);
      
      const res = await fetch('http://localhost:8000/api/projects', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      // Navigate straight into the new project
      navigate(`/project/${data.id}`);
    } catch (err) {
      console.error("Failed to create project", err);
    }
  };

  if (loading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 text-blue-500 animate-spin" /></div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
        <button 
          onClick={() => setIsCreating(!isCreating)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium text-sm flex items-center transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4 mr-2" /> New Project
        </button>
      </div>

      {/* Inline Create Form */}
      {isCreating && (
        <form onSubmit={handleCreateProject} className="mb-8 bg-white p-6 rounded-2xl shadow-sm border border-gray-200 flex items-end space-x-4">
          <div className="flex-1">
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Project Name</label>
            <input 
              type="text" 
              autoFocus
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="e.g., Q3 Vendor Agreements" 
              className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
          <button type="submit" className="bg-gray-900 hover:bg-black text-white px-6 py-2 rounded-lg font-medium transition-colors">
            Create
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {projects.length === 0 && !isCreating ? (
          <div className="col-span-3 text-center py-12 text-gray-500 bg-white rounded-2xl border border-gray-200 border-dashed">
            No projects yet. Create one to get started.
          </div>
        ) : (
          projects.map(p => (
            <button 
              key={p.id} 
              onClick={() => navigate(`/project/${p.id}`)}
              className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-500/30 transition-all text-left group"
            >
              <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <FolderGit2 className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-lg mb-1">{p.name}</h3>
              <div className="flex justify-between items-center text-xs text-gray-500 mt-4 pt-4 border-t border-gray-100">
                <span className="font-medium bg-gray-100 px-2 py-1 rounded">{p.docCount} documents</span>
                <span>{new Date(p.created_at).toLocaleDateString()}</span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
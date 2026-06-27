import React from 'react';
import { FolderGit2, Plus } from 'lucide-react';

export default function ProjectsList({ projects, onOpenProject }) {
  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
        <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium text-sm flex items-center transition-colors shadow-sm">
          <Plus className="w-4 h-4 mr-2" /> New Project
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {projects.map(p => (
          <button 
            key={p.id} 
            onClick={() => onOpenProject(p.id)}
            className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 hover:shadow-md hover:border-gray-300 transition-all text-left group"
          >
            <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-lg mb-1">{p.name}</h3>
            <div className="flex justify-between items-center text-xs text-gray-500 mt-4">
              <span>{p.docCount} documents</span>
              <span>{p.updatedAt}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
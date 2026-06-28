import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useParams } from 'react-router-dom';
import { Database, ChevronRight } from 'lucide-react';
import ProjectsList from './views/ProjectsList';
import ProjectDetail from './views/ProjectDetail';
import DocumentWorkspace from './views/DocumentWorkspace';

// A dynamic breadcrumb component based on route
function Breadcrumbs() {
  const { projectId, docId } = useParams();
  
  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50 shadow-sm h-14 flex items-center px-6 shrink-0">
      <div className="flex items-center space-x-2 text-sm font-medium">
        <Link to="/" className="flex items-center text-gray-900 hover:text-blue-600 transition-colors">
          <Database className="w-4 h-4 mr-2" /> Projects
        </Link>
        
        {projectId && (
          <>
            <ChevronRight className="w-4 h-4 text-gray-400" />
            <Link to={`/project/${projectId}`} className="text-gray-500 hover:text-blue-600 transition-colors">
              Project Details
            </Link>
          </>
        )}

        {docId && (
          <>
            <ChevronRight className="w-4 h-4 text-gray-400" />
            <span className="text-gray-400">Analysis</span>
          </>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[#F5F5F7] font-sans text-gray-900 flex flex-col">
        {/* We use a wildcard route just to grab the params for the Breadcrumbs */}
        <Routes>
          <Route path="/*" element={<Breadcrumbs />} />
        </Routes>

        <main className="flex-1 overflow-hidden relative">
          <Routes>
            <Route path="/" element={<ProjectsList />} />
            <Route path="/project/:projectId" element={<ProjectDetail />} />
            <Route path="/document/:docId" element={<DocumentWorkspace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
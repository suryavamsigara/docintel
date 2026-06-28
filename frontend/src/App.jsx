import React, { useState } from 'react';
import { Database, ChevronRight } from 'lucide-react';
import { useProjectStore } from './hooks/useProjectStore';
import ProjectsList from './views/ProjectsList';
import ProjectDetail from './views/ProjectDetail';
import DocumentWorkspace from './views/DocumentWorkspace';

export default function App() {
  const store = useProjectStore();
  
  // View routing state: 'PROJECTS', 'PROJECT_DETAIL', 'WORKSPACE'
  const [currentView, setCurrentView] = useState('PROJECTS');
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeDocId, setActiveDocId] = useState(null);

  const activeProject = store.projects.find(p => p.id === activeProjectId);
  const activeDocument = store.documents[activeDocId];

  return (
    <div className="min-h-screen bg-[#F5F5F7] font-sans text-gray-900 selection:bg-blue-500 selection:text-white flex flex-col">
      {/* Top Navbar & Breadcrumbs */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50 shadow-sm h-14 flex items-center px-6 shrink-0">
        <div className="flex items-center space-x-2 text-sm font-medium">
          <button onClick={() => setCurrentView('PROJECTS')} className="flex items-center text-gray-900 hover:text-blue-600 transition-colors">
            <Database className="w-4 h-4 mr-2" /> Projects
          </button>
          
          {activeProject && currentView !== 'PROJECTS' && (
            <>
              <ChevronRight className="w-4 h-4 text-gray-400" />
              <button 
                onClick={() => setCurrentView('PROJECT_DETAIL')}
                className={`transition-colors ${currentView === 'PROJECT_DETAIL' ? 'text-gray-900' : 'text-gray-500 hover:text-blue-600'}`}
              >
                {activeProject.name}
              </button>
            </>
          )}

          {activeDocument && currentView === 'WORKSPACE' && (
            <>
              <ChevronRight className="w-4 h-4 text-gray-400" />
              <span className="text-gray-500 truncate max-w-xs">{activeDocument.name}</span>
            </>
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        {currentView === 'PROJECTS' && (
          <ProjectsList 
            projects={store.projects} 
            onOpenProject={(id) => { setActiveProjectId(id); setCurrentView('PROJECT_DETAIL'); }} 
          />
        )}
        
        {currentView === 'PROJECT_DETAIL' && (
          <ProjectDetail 
            project={activeProject}
            documents={Object.values(store.documents).filter(d => d.projectId === activeProject.id)}
            // UPDATE THIS LINE TO PASS MODE:
            onUpload={(file, mode) => store.uploadDocument(activeProject.id, file, mode)}
            onOpenDoc={(id) => { setActiveDocId(id); setCurrentView('WORKSPACE'); }}
          />
        )}

        {currentView === 'WORKSPACE' && (
          <DocumentWorkspace document={activeDocument} />
        )}
      </main>
    </div>
  );
}
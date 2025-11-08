import { BrowserRouter, Routes, Route } from 'react-router-dom';
import '@/App.css';
import Dashboard from './pages/Dashboard';
import RepositoryView from './pages/RepositoryView';
import AnalysisView from './pages/AnalysisView';
import { Toaster } from './components/ui/sonner';

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/repository/:repoId" element={<RepositoryView />} />
          <Route path="/analysis/:analysisId" element={<AnalysisView />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
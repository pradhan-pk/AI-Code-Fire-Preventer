import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GitBranch, Plus, Trash2, Eye, Loader2, GitCommit, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const navigate = useNavigate();
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    github_token: '',
    branch: 'main'
  });
  const [submitting, setSubmitting] = useState(false);
  const [health, setHealth] = useState({ api: 'checking', ollama: 'checking' });

  useEffect(() => {
    fetchRepositories();
    checkHealth();
    const interval = setInterval(fetchRepositories, 5000);
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const response = await axios.get(`${API}/health`);
      setHealth(response.data);
    } catch (error) {
      setHealth({ api: 'error', ollama: 'disconnected' });
    }
  };

  const fetchRepositories = async () => {
    try {
      const response = await axios.get(`${API}/repositories`);
      setRepositories(response.data);
      setLoading(false);
    } catch (error) {
      toast.error('Failed to fetch repositories');
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      await axios.post(`${API}/repositories`, formData);
      toast.success('Repository added successfully! Analysis started...');
      setIsDialogOpen(false);
      setFormData({ name: '', url: '', github_token: '', branch: 'main' });
      fetchRepositories();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add repository');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (repoId) => {
    if (!window.confirm('Are you sure you want to delete this repository?')) return;

    try {
      await axios.delete(`${API}/repositories/${repoId}`);
      toast.success('Repository deleted successfully');
      fetchRepositories();
    } catch (error) {
      toast.error('Failed to delete repository');
    }
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      pending: { label: 'Pending', className: 'status-badge status-pending' },
      analyzing: { label: 'Analyzing', className: 'status-badge status-analyzing' },
      completed: { label: 'Completed', className: 'status-badge status-completed' },
      error: { label: 'Error', className: 'status-badge status-error' }
    };
    const config = statusMap[status] || statusMap.pending;
    return <span className={config.className} data-testid={`repo-status-${status}`}>{config.label}</span>;
  };

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="glass-card p-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold gradient-text mb-2" data-testid="dashboard-title">
                AI Code Impact Analyzer
              </h1>
              <p className="text-slate-400 text-lg">
                Detect breaking changes across module dependencies using AI
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${health.api === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-slate-400">API</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${health.ollama === 'connected' ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-slate-400">Ollama</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Add Repository Button */}
      <div className="max-w-7xl mx-auto mb-6">
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-repo-button">
              <Plus className="w-4 h-4 mr-2" />
              Add Repository
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-slate-900 border-slate-700" data-testid="add-repo-dialog">
            <DialogHeader>
              <DialogTitle className="text-2xl text-slate-100">Add GitHub Repository</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div>
                <Label htmlFor="name" className="text-slate-300">Repository Name</Label>
                <Input
                  id="name"
                  data-testid="repo-name-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="my-project"
                  className="bg-slate-800 border-slate-700 text-slate-100"
                  required
                />
              </div>
              <div>
                <Label htmlFor="url" className="text-slate-300">GitHub URL</Label>
                <Input
                  id="url"
                  data-testid="repo-url-input"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="https://github.com/username/repo"
                  className="bg-slate-800 border-slate-700 text-slate-100"
                  required
                />
              </div>
              <div>
                <Label htmlFor="token" className="text-slate-300">GitHub Personal Access Token</Label>
                <Input
                  id="token"
                  data-testid="repo-token-input"
                  type="password"
                  value={formData.github_token}
                  onChange={(e) => setFormData({ ...formData, github_token: e.target.value })}
                  placeholder="ghp_xxxxxxxxxxxx"
                  className="bg-slate-800 border-slate-700 text-slate-100"
                  required
                />
              </div>
              <div>
                <Label htmlFor="branch" className="text-slate-300">Branch</Label>
                <Input
                  id="branch"
                  data-testid="repo-branch-input"
                  value={formData.branch}
                  onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                  placeholder="main"
                  className="bg-slate-800 border-slate-700 text-slate-100"
                  required
                />
              </div>
              <Button type="submit" disabled={submitting} className="w-full bg-blue-600 hover:bg-blue-700" data-testid="submit-repo-button">
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Adding...
                  </>
                ) : (
                  'Add Repository'
                )}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Repositories Grid */}
      <div className="max-w-7xl mx-auto">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : repositories.length === 0 ? (
          <Card className="glass-card border-slate-700">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <AlertCircle className="w-16 h-16 text-slate-600 mb-4" />
              <p className="text-slate-400 text-lg">No repositories added yet</p>
              <p className="text-slate-500 text-sm">Click "Add Repository" to get started</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {repositories.map((repo) => (
              <Card key={repo.id} className="glass-card border-slate-700 hover-lift" data-testid={`repo-card-${repo.id}`}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-xl text-slate-100 mb-2" data-testid="repo-name">{repo.name}</CardTitle>
                      <CardDescription className="text-slate-400 flex items-center gap-2">
                        <GitBranch className="w-4 h-4" />
                        {repo.branch}
                      </CardDescription>
                    </div>
                    {getStatusBadge(repo.status)}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-800/50 p-3 rounded-lg">
                        <p className="text-slate-500 text-xs mb-1">Modules</p>
                        <p className="text-2xl font-bold text-slate-100" data-testid="modules-count">{repo.modules_count}</p>
                      </div>
                      <div className="bg-slate-800/50 p-3 rounded-lg">
                        <p className="text-slate-500 text-xs mb-1">Dependencies</p>
                        <p className="text-2xl font-bold text-slate-100" data-testid="dependencies-count">{repo.dependencies_count}</p>
                      </div>
                    </div>

                    {repo.last_analyzed && (
                      <p className="text-xs text-slate-500">
                        Last analyzed: {new Date(repo.last_analyzed).toLocaleString()}
                      </p>
                    )}

                    <div className="flex gap-2">
                      <Button
                        onClick={() => navigate(`/repository/${repo.id}`)}
                        className="flex-1 bg-slate-700 hover:bg-slate-600"
                        disabled={repo.status !== 'completed'}
                        data-testid="view-repo-button"
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        View Details
                      </Button>
                      <Button
                        onClick={() => handleDelete(repo.id)}
                        variant="destructive"
                        size="icon"
                        data-testid="delete-repo-button"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
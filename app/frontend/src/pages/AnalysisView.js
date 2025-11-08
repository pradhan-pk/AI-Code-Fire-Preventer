import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ArrowLeft, Loader2, FileCode, AlertTriangle, CheckCircle2, Info, Shield } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function AnalysisView() {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalysis();
  }, [analysisId]);

  const fetchAnalysis = async () => {
    try {
      const response = await axios.get(`${API}/analyses/${analysisId}`);
      setAnalysis(response.data);
      setLoading(false);
    } catch (error) {
      toast.error('Failed to fetch analysis');
      setLoading(false);
    }
  };

  const getRiskBadge = (risk) => {
    const riskConfig = {
      low: { icon: CheckCircle2, className: 'risk-low' },
      medium: { icon: Info, className: 'risk-medium' },
      high: { icon: AlertTriangle, className: 'risk-high' },
      critical: { icon: Shield, className: 'risk-critical' }
    };
    const config = riskConfig[risk] || riskConfig.medium;
    const Icon = config.icon;
    return (
      <span className={`status-badge ${config.className} flex items-center gap-2`} data-testid="risk-badge">
        <Icon className="w-4 h-4" />
        {risk.toUpperCase()}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="glass-card border-slate-700 max-w-md">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <AlertTriangle className="w-16 h-16 text-red-500 mb-4" />
            <p className="text-slate-300 text-lg">Analysis not found</p>
            <Button onClick={() => navigate('/')} className="mt-4">Go to Dashboard</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center gap-4 mb-4">
            <Button onClick={() => navigate(`/repository/${analysis.repo_id}`)} variant="ghost" size="icon" data-testid="back-button">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-slate-100" data-testid="analysis-title">
                Impact Analysis Report
              </h1>
              <p className="text-slate-400 mt-1">
                {analysis.analysis_type === 'commit' ? 'Commit' : 'Pull Request'}: {analysis.reference}
              </p>
            </div>
            {getRiskBadge(analysis.risk_level)}
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <span>Analyzed at: {new Date(analysis.created_at).toLocaleString()}</span>
            <span>•</span>
            <span>{analysis.changed_files.length} files changed</span>
            <span>•</span>
            <span>{analysis.impacted_modules.length} modules impacted</span>
          </div>
        </div>

        {/* Changed Files */}
        <Card className="glass-card border-slate-700 mb-6">
          <CardHeader>
            <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
              <FileCode className="w-6 h-6 text-blue-400" />
              Changed Files
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {analysis.changed_files.map((file, idx) => (
                <div key={idx} className="bg-slate-800/50 p-3 rounded-lg font-mono text-sm text-slate-300" data-testid="changed-file">
                  {file}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Impacted Modules */}
        <Card className="glass-card border-slate-700 mb-6">
          <CardHeader>
            <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-orange-400" />
              Impacted Modules ({analysis.impacted_modules.length})
            </CardTitle>
            <CardDescription className="text-slate-400">
              Modules that may be affected by these changes
            </CardDescription>
          </CardHeader>
          <CardContent>
            {analysis.impacted_modules.length === 0 ? (
              <div className="text-center py-8">
                <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="text-slate-300">No impacted modules detected</p>
                <p className="text-slate-500 text-sm mt-1">Changes appear to be isolated</p>
              </div>
            ) : (
              <Accordion type="single" collapsible className="space-y-3">
                {analysis.impacted_modules.map((module, idx) => (
                  <AccordionItem
                    key={idx}
                    value={`module-${idx}`}
                    className="bg-slate-800/30 rounded-lg border border-slate-700"
                    data-testid="impacted-module"
                  >
                    <AccordionTrigger className="px-4 hover:no-underline">
                      <div className="flex items-center justify-between w-full pr-4">
                        <span className="text-slate-100 font-medium">{module.module}</span>
                        <Badge variant="outline" className="text-orange-400 border-orange-400">
                          {module.confidence || 'medium'} confidence
                        </Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="px-4 pb-4">
                      <div className="space-y-3">
                        <div>
                          <p className="text-slate-400 text-sm mb-2">Module Path:</p>
                          <p className="text-slate-300 font-mono text-sm bg-slate-900/50 p-2 rounded">
                            {module.module_path}
                          </p>
                        </div>
                        <div>
                          <p className="text-slate-400 text-sm mb-2">Affected Files:</p>
                          <div className="space-y-1">
                            {module.affected_files.map((file, fileIdx) => (
                              <div key={fileIdx} className="text-slate-300 font-mono text-sm bg-slate-900/50 p-2 rounded">
                                {file}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card className="glass-card border-slate-700">
          <CardHeader>
            <CardTitle className="text-xl text-slate-100 flex items-center gap-2">
              <Shield className="w-6 h-6 text-green-400" />
              Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analysis.recommendations.map((recommendation, idx) => (
                <div key={idx} className="flex gap-3 bg-slate-800/30 p-4 rounded-lg" data-testid="recommendation">
                  <div className="flex-shrink-0 w-6 h-6 bg-green-500/20 rounded-full flex items-center justify-center text-green-400 font-bold text-sm">
                    {idx + 1}
                  </div>
                  <p className="text-slate-300 flex-1">{recommendation}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
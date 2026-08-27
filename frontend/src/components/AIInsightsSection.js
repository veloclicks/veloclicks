'use client';
import React, { useState } from 'react';
import { Sparkles, RefreshCw, Lock, Copy, Check } from 'lucide-react';

const AIInsightsSection = ({ activityId, isPremiumUser, colors }) => {
  const [activeTab, setActiveTab] = useState('insight');
  const [insights, setInsights] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  const [copied, setCopied] = useState(false);

  const authHeaders = {
    'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
    'Content-Type': 'application/json',
  };

  const handleGenerate = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/ai-coach/activity/${activityId}`,
        { headers: authHeaders }
      );
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to generate insights');
      }
      const data = await response.json();
      setInsights(data.coaching);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSummary = async () => {
    if (summary) return;
    try {
      setSummaryLoading(true);
      setSummaryError(null);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/ai-coach/activity/${activityId}/summary`,
        { headers: authHeaders }
      );
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to load activity summary');
      }
      const data = await response.json();
      setSummary(data.summary);
    } catch (err) {
      setSummaryError(err.message);
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleCopySummary = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(summary, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy summary:', err);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'summary') handleLoadSummary();
  };

  const tabs = [
    { id: 'insight', label: 'AI Insight' },
    { id: 'summary', label: 'Activity Summary' },
  ];

  return (
    <div
      className="mt-6 rounded-xl shadow-sm"
      style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}
    >
      <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>
            AI Training Insights
          </h3>
          <Sparkles className="h-5 w-5" style={{ color: colors.accent }} />
        </div>
      </div>

      <div className="p-6">
        {!isPremiumUser ? (
          <div className="text-center py-8">
            <Lock className="h-12 w-12 mx-auto mb-4" style={{ color: colors.mutedForeground }} />
            <p className="text-sm mb-2" style={{ color: colors.mutedForeground }}>
              AI-powered training insights are available for Premium members
            </p>
            <p className="text-xs" style={{ color: colors.mutedForeground }}>
              Upgrade to Premium to get personalized analysis and recommendations
            </p>
          </div>
        ) : (
          <>
            {insights && (
              <div className="flex border-b mb-4" style={{ borderColor: colors.border }}>
                {tabs.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => handleTabChange(tab.id)}
                    className="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
                    style={{
                      borderColor: activeTab === tab.id ? colors.accent : 'transparent',
                      color: activeTab === tab.id ? colors.accent : colors.mutedForeground,
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            {activeTab === 'insight' && (
              insights ? (
                <div className="prose prose-xs max-w-none" style={{ color: colors.foreground }}>
                  <div className="whitespace-pre-wrap">{insights}</div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-sm mb-4" style={{ color: colors.mutedForeground }}>
                    Get AI-powered analysis of your training session with personalized insights and recommendations
                  </p>
                  <button
                    onClick={handleGenerate}
                    disabled={loading}
                    className="px-6 py-3 rounded-lg font-medium transition-colors hover:opacity-90 disabled:opacity-50"
                    style={{ backgroundColor: colors.accent, color: 'white' }}
                  >
                    {loading ? (
                      <span className="flex items-center space-x-2">
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Generating...</span>
                      </span>
                    ) : (
                      <span className="flex items-center space-x-2">
                        <Sparkles className="h-4 w-4" />
                        <span>View AI Insights</span>
                      </span>
                    )}
                  </button>
                  {error && <p className="mt-4 text-sm text-red-500">{error}</p>}
                </div>
              )
            )}

            {activeTab === 'summary' && (
              summaryLoading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin" style={{ color: colors.mutedForeground }} />
                </div>
              ) : summaryError ? (
                <p className="text-sm text-red-500 py-4">{summaryError}</p>
              ) : summary ? (
                <div className="relative">
                  <button
                    onClick={handleCopySummary}
                    className="absolute top-2 right-2 p-2 rounded-lg transition-colors hover:opacity-80"
                    style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}
                    title="Copy JSON to clipboard"
                  >
                    {copied ? (
                      <Check className="h-4 w-4" style={{ color: colors.accent }} />
                    ) : (
                      <Copy className="h-4 w-4" style={{ color: colors.mutedForeground }} />
                    )}
                  </button>
                  <pre
                    className="text-xs overflow-auto rounded-lg p-4"
                    style={{ backgroundColor: colors.background, color: colors.foreground, maxHeight: '480px' }}
                  >
                    {JSON.stringify(summary, null, 2)}
                  </pre>
                </div>
              ) : null
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AIInsightsSection;

'use client';
import React, { useState } from 'react';
import { Sparkles, RefreshCw, Lock } from 'lucide-react';

const AIInsightsSection = ({ activityId, isPremiumUser, colors }) => {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerateInsights = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = localStorage.getItem('authToken');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/ai-coach/activity/${activityId}?mode=llm`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
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

  return (
    <div
      className="mt-6 rounded-xl shadow-sm"
      style={{
        backgroundColor: colors.card,
        border: `1px solid ${colors.border}`,
      }}
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
        ) : !insights ? (
          <div className="text-center py-8">
            <p className="text-sm mb-4" style={{ color: colors.mutedForeground }}>
              Get AI-powered analysis of your training session with personalized insights and recommendations
            </p>
            <button
              onClick={handleGenerateInsights}
              disabled={loading}
              className="px-6 py-3 rounded-lg font-medium transition-colors hover:opacity-90 disabled:opacity-50"
              style={{ backgroundColor: colors.accent, color: 'white' }}
            >
              {loading ? (
                <span className="flex items-center space-x-2">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Generating insights...</span>
                </span>
              ) : (
                <span className="flex items-center space-x-2">
                  <Sparkles className="h-4 w-4" />
                  <span>Generate AI Insights</span>
                </span>
              )}
            </button>
            {error && (
              <p className="mt-4 text-sm text-red-500">{error}</p>
            )}
          </div>
        ) : (
          <div>
            <div
              className="prose prose-xs max-w-none"
              style={{ color: colors.foreground }}
            >
              <div className="whitespace-pre-wrap">{insights}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AIInsightsSection;

'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Navigation from '../../components/Navigation';
import { Brain, Save, Check } from 'lucide-react';

const AIInsightsPage = () => {
  const router = useRouter();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState(null);
  const [rpeValues, setRpeValues] = useState({}); // Map of activity_id -> rpe value

  const colors = {
    background: 'hsl(210, 10%, 15%)',
    card: 'hsl(210, 10%, 20%)',
    foreground: 'hsl(210, 25%, 96.5%)',
    primary: 'hsl(207, 44%, 49%)',
    accent: 'hsl(16, 100%, 66%)',
    muted: 'hsl(210, 10%, 25%)',
    mutedForeground: 'hsl(210, 15%, 65%)',
    border: 'hsl(210, 10%, 30%)',
    chart3: 'hsl(173, 58%, 39%)',
  };

  // RPE emoji mapping with descriptive labels
  const rpeScale = [
    { value: 1, emoji: '😌', label: 'Very Easy', color: '#4ade80' },
    { value: 2, emoji: '😊', label: 'Very Easy', color: '#4ade80' },
    { value: 3, emoji: '🙂', label: 'Easy', color: '#86efac' },
    { value: 4, emoji: '😐', label: 'Easy', color: '#86efac' },
    { value: 5, emoji: '😅', label: 'Moderate', color: '#fbbf24' },
    { value: 6, emoji: '😓', label: 'Moderate', color: '#fbbf24' },
    { value: 7, emoji: '😰', label: 'Hard', color: '#fb923c' },
    { value: 8, emoji: '😫', label: 'Hard', color: '#fb923c' },
    { value: 9, emoji: '😵', label: 'Very Hard', color: '#f87171' },
    { value: 10, emoji: '💀', label: 'Very Hard', color: '#f87171' },
  ];

  useEffect(() => {
    fetchRecentActivities();
  }, []);

  const fetchRecentActivities = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      // Calculate years to fetch (current year for now, we'll filter client-side)
      const currentYear = new Date().getFullYear();

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/strava/activities/?years=${currentYear}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch activities');
      }

      const data = await response.json();

      // The API returns an array directly, not {activities: [...]}
      const activitiesArray = Array.isArray(data) ? data : [];

      // Filter to last 2 weeks only
      const now = new Date();
      const twoWeeksAgo = new Date(now);
      twoWeeksAgo.setDate(now.getDate() - 14);

      const recentActivities = activitiesArray.filter(activity => {
        const activityDate = new Date(activity.start_date_local);
        return activityDate >= twoWeeksAgo && activityDate <= now;
      });

      // Sort by date descending (most recent first)
      const sortedActivities = recentActivities.sort((a, b) => {
        return new Date(b.start_date_local) - new Date(a.start_date_local);
      });

      setActivities(sortedActivities);

      // Initialize RPE values from existing data
      const initialRpeValues = {};
      sortedActivities.forEach(activity => {
        if (activity.rpe !== null && activity.rpe !== undefined) {
          initialRpeValues[activity.id] = activity.rpe;
        }
      });
      setRpeValues(initialRpeValues);

    } catch (err) {
      console.error('Error fetching activities:', err);
      setError('Failed to load activities. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRpeChange = (activityId, rpeValue) => {
    setRpeValues(prev => ({
      ...prev,
      [activityId]: rpeValue
    }));
  };

  const handleSaveAll = async () => {
    try {
      setSaving(true);
      setSaveSuccess(false);
      setError(null);

      const token = localStorage.getItem('authToken');

      // Build updates array from rpeValues
      const updates = Object.entries(rpeValues).map(([activity_id, rpe]) => ({
        activity_id: parseInt(activity_id),
        rpe: rpe
      }));

      if (updates.length === 0) {
        setError('No RPE values to save');
        return;
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/strava/activities/rpe`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ updates })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to save RPE values');
      }

      const result = await response.json();
      setSaveSuccess(true);

      // Show success message briefly
      setTimeout(() => setSaveSuccess(false), 3000);

    } catch (err) {
      console.error('Error saving RPE values:', err);
      setError(err.message || 'Failed to save RPE values. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center" style={{ color: colors.mutedForeground }}>
            Loading activities...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      <Navigation />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center space-x-3 mb-2">
            <Brain className="h-8 w-8" style={{ color: colors.accent }} />
            <h1 className="text-3xl font-bold" style={{ color: colors.foreground }}>
              AI Insights - Rate Your Activities
            </h1>
          </div>
          <p className="text-sm" style={{ color: colors.mutedForeground }}>
            Rate the perceived exertion (RPE) of your recent activities. This helps our AI understand your training load and provide better insights.
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: '#7f1d1d', border: '1px solid #991b1b' }}>
            <p className="text-sm text-red-200">{error}</p>
          </div>
        )}

        {/* Success Message */}
        {saveSuccess && (
          <div className="mb-4 p-4 rounded-lg flex items-center space-x-2" style={{ backgroundColor: '#14532d', border: '1px solid #166534' }}>
            <Check className="h-5 w-5 text-green-200" />
            <p className="text-sm text-green-200">RPE values saved successfully!</p>
          </div>
        )}

        {/* Activities Table */}
        <div className="rounded-xl shadow-lg overflow-hidden" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr style={{ backgroundColor: colors.muted, borderBottom: `1px solid ${colors.border}` }}>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: colors.mutedForeground }}>
                    Activity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: colors.mutedForeground }}>
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: colors.mutedForeground }}>
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: colors.mutedForeground }}>
                    Norm. Power
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider" style={{ color: colors.mutedForeground }}>
                    Rate Perceived Exertion (1-10)
                  </th>
                </tr>
              </thead>
              <tbody>
                {activities.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center" style={{ color: colors.mutedForeground }}>
                      No activities found in the last 2 weeks
                    </td>
                  </tr>
                ) : (
                  activities.map((activity, index) => (
                    <tr
                      key={activity.id}
                      style={{
                        borderBottom: index !== activities.length - 1 ? `1px solid ${colors.border}` : 'none',
                        backgroundColor: index % 2 === 0 ? colors.card : colors.muted
                      }}
                    >
                      <td className="px-6 py-4">
                        <button
                          onClick={() => router.push(`/activities/${activity.id}`)}
                          className="text-sm font-medium hover:underline text-left"
                          style={{ color: colors.primary }}
                        >
                          {activity.name}
                        </button>
                      </td>
                      <td className="px-6 py-4 text-sm" style={{ color: colors.foreground }}>
                        {formatDate(activity.start_date_local)}
                      </td>
                      <td className="px-6 py-4 text-sm" style={{ color: colors.foreground }}>
                        {formatDuration(activity.moving_time)}
                      </td>
                      <td className="px-6 py-4 text-sm" style={{ color: colors.accent }}>
                        {activity.weighted_average_watts ? `${Math.round(activity.weighted_average_watts)}W` : '-'}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center space-x-1">
                          {rpeScale.map((rpe) => (
                            <button
                              key={rpe.value}
                              onClick={() => handleRpeChange(activity.id, rpe.value)}
                              className="relative group"
                              style={{
                                fontSize: '24px',
                                padding: '4px',
                                borderRadius: '6px',
                                border: rpeValues[activity.id] === rpe.value
                                  ? `2px solid ${rpe.color}`
                                  : '2px solid transparent',
                                backgroundColor: rpeValues[activity.id] === rpe.value
                                  ? colors.muted
                                  : 'transparent',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                              }}
                              title={`${rpe.value} - ${rpe.label}`}
                            >
                              <span style={{
                                opacity: rpeValues[activity.id] === rpe.value ? 1 : 0.5,
                                display: 'block'
                              }}>
                                {rpe.emoji}
                              </span>
                              {/* Tooltip */}
                              <span className="absolute -top-8 left-1/2 transform -translate-x-1/2 px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
                                style={{ backgroundColor: colors.muted, color: colors.foreground, border: `1px solid ${colors.border}` }}>
                                {rpe.value} - {rpe.label}
                              </span>
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Save Button */}
          {activities.length > 0 && (
            <div className="px-6 py-4 flex justify-end" style={{ backgroundColor: colors.muted, borderTop: `1px solid ${colors.border}` }}>
              <button
                onClick={handleSaveAll}
                disabled={saving || Object.keys(rpeValues).length === 0}
                className="flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                style={{ backgroundColor: colors.accent, color: 'white' }}
              >
                {saving ? (
                  <>
                    <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="h-5 w-5" />
                    <span>Save All RPE Values</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* RPE Scale Legend */}
        <div className="mt-6 rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
            RPE Scale Reference
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { range: '1-2', label: 'Very Easy', emoji: '😌😊', description: 'Recovery pace' },
              { range: '3-4', label: 'Easy', emoji: '🙂😐', description: 'Comfortable endurance' },
              { range: '5-6', label: 'Moderate', emoji: '😅😓', description: 'Steady tempo' },
              { range: '7-8', label: 'Hard', emoji: '😰😫', description: 'Challenging effort' },
              { range: '9-10', label: 'Very Hard', emoji: '😵💀', description: 'Maximum effort' },
            ].map((item, index) => (
              <div key={index} className="text-center">
                <div className="text-2xl mb-1">{item.emoji}</div>
                <div className="text-sm font-semibold" style={{ color: colors.foreground }}>{item.range}</div>
                <div className="text-xs" style={{ color: colors.primary }}>{item.label}</div>
                <div className="text-xs mt-1" style={{ color: colors.mutedForeground }}>{item.description}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIInsightsPage;

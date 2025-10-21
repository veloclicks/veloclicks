'use client';
import React, { useState, useMemo, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Navigation from '../../components/Navigation';
import { ChevronUp, ChevronDown, Filter, TrendingUp, Activity, RefreshCw, User } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useAuth } from '../../contexts/AuthContext';
import { demoActivitiesData } from '../../data/demoActivities';

const ActivitiesContent = () => {
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [selectedYears, setSelectedYears] = useState(['2024', '2025']); // Default to recent years
  const [minElapsedTime, setMinElapsedTime] = useState(0);
  const [minNormalisedPower, setMinNormalisedPower] = useState(0);
  const [showFilters, setShowFilters] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // Check for Strava connection success
  useEffect(() => {
    const stravaConnected = searchParams.get('strava_connected');
    const activitiesCount = searchParams.get('activities');

    if (stravaConnected === 'true') {
      const count = activitiesCount ? parseInt(activitiesCount) : 0;
      setSuccessMessage(`Strava connected successfully! ${count} activities synced.`);
      setShowSuccessToast(true);

      // Auto-hide toast after 5 seconds
      setTimeout(() => {
        setShowSuccessToast(false);
      }, 5000);

      // Clean up URL parameters
      const url = new URL(window.location);
      url.searchParams.delete('strava_connected');
      url.searchParams.delete('activities');
      window.history.replaceState({}, document.title, url.pathname);
    }
  }, [searchParams]);

  // Fetch activities from Flask API or use demo data
  const fetchActivities = async (years = null) => {
    try {
      setLoading(true);

      // Check if demo user - if so, use demo data
      if (user?.email === process.env.NEXT_PUBLIC_DEMO_EMAIL) {
        // Filter demo data by selected years if provided
        let filteredData = demoActivitiesData;
        if (years && years.length > 0) {
          filteredData = demoActivitiesData.filter(activity => {
            const activityYear = new Date(activity.dateTime).getFullYear();
            return years.includes(activityYear.toString());
          });
        }

        setActivities(filteredData);
        setLoading(false);
        return;
      }

      // For real users, fetch from API
      let url = `${process.env.NEXT_PUBLIC_API_URL}/strava/activities/`;
      if (years && years.length > 0) {
        url += `?years=${years.join(',')}`;
      }

      const token = localStorage.getItem('authToken');
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch activities');
      }
      const data = await response.json();

      // Transform backend data to frontend format
      const transformedActivities = data.map(activity => ({
        id: activity.id,
        name: activity.name,
        dateTime: activity.start_date_local || activity.start_date,
        elapsedTime: Math.round((activity.elapsed_time || 0) / 60), // Convert seconds to minutes
        distance: activity.distance || 0,
        avgSpeed: activity.average_speed || 0,
        elevationGain: activity.total_elevation_gain || 0,
        avgPower: activity.average_watts || 0,
        normalisedPower: activity.weighted_average_watts || 0
      }));

      setActivities(transformedActivities);
    } catch (err) {
      setError(err.message);
      console.error('Failed to fetch activities:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities(selectedYears);
  }, [selectedYears]); // Refetch when years selection changes

  // Check for refresh parameter and refetch if present
  useEffect(() => {
    const shouldRefresh = searchParams.get('refresh');
    if (shouldRefresh === 'true') {
      fetchActivities(selectedYears);
      // Remove the refresh parameter from URL without causing a page reload
      const newUrl = window.location.pathname;
      window.history.replaceState(null, '', newUrl);
    }
  }, [searchParams]);

  // Dark theme colors matching your palette
  const colors = {
    background: 'hsl(210, 10%, 15%)',
    card: 'hsl(210, 10%, 20%)',
    foreground: 'hsl(210, 25%, 96.5%)',
    primary: 'hsl(207, 44%, 49%)',
    accent: 'hsl(16, 100%, 66%)',
    chart3: 'hsl(173, 58%, 39%)',
    muted: 'hsl(210, 10%, 25%)',
    mutedForeground: 'hsl(210, 15%, 65%)',
    border: 'hsl(210, 10%, 30%)',
  };

  // Fixed available years from 2018 to 2025
  const availableYears = ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025'];

  // Format elapsed time
  const formatElapsedTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  };

  // Sort function
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // Filter and sort activities (year filtering now handled by backend)
  const filteredAndSortedActivities = useMemo(() => {
    let filtered = activities.filter(activity => {
      const matchesSearch = searchTerm === '' ||
        (activity.name && activity.name.toLowerCase().includes(searchTerm.toLowerCase()));

      return activity.elapsedTime >= minElapsedTime &&
             activity.normalisedPower >= minNormalisedPower &&
             matchesSearch;
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];
        
        if (sortConfig.key === 'dateTime') {
          aValue = new Date(aValue);
          bValue = new Date(bValue);
        }
        
        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [activities, minElapsedTime, minNormalisedPower, sortConfig, searchTerm]);

  const SortIcon = ({ column }) => {
    const iconColor = sortConfig.key === column ? colors.primary : colors.mutedForeground;
    if (sortConfig.key !== column) {
      return <ChevronUp className="w-4 h-4" style={{ color: iconColor }} />;
    }
    return sortConfig.direction === 'asc' ? 
      <ChevronUp className="w-4 h-4" style={{ color: iconColor }} /> : 
      <ChevronDown className="w-4 h-4" style={{ color: iconColor }} />;
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      <Navigation />

      {/* Success Toast */}
      {showSuccessToast && (
        <div className="fixed top-4 right-4 z-50">
          <div
            className="bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg flex items-center space-x-3 animate-pulse"
          >
            <Activity className="h-5 w-5" />
            <span className="font-medium">{successMessage}</span>
            <button
              onClick={() => setShowSuccessToast(false)}
              className="ml-2 text-white hover:text-gray-200"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Page Title */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold" style={{ color: colors.foreground }}>Training Activities</h1>
          <p className="text-sm mt-1" style={{ color: colors.mutedForeground }}>
            View and analyze your training activities
          </p>
          {loading && (
            <p className="text-sm mt-2" style={{ color: colors.primary }}>
              Loading activities...
            </p>
          )}
          {error && (
            <p className="text-sm mt-2" style={{ color: colors.accent }}>
              Error: {error}
            </p>
          )}
        </div>

        {/* Filters */}
        <div className="rounded-xl shadow-sm mb-6" style={{ 
          backgroundColor: colors.card, 
          border: `1px solid ${colors.border}` 
        }}>
          <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center transition-colors hover:opacity-80"
              style={{ color: colors.primary }}
            >
              <Filter className="w-5 h-5 mr-2" style={{ color: colors.primary }} />
              <span className="font-semibold">Filters & Controls</span>
              {showFilters ? <ChevronUp className="w-4 h-4 ml-2" /> : <ChevronDown className="w-4 h-4 ml-2" />}
            </button>
          </div>
          
          {showFilters && (
            <div className="p-6">
              {/* Search Input */}
              <div className="mb-6">
                <label className="block text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
                  <span className="flex items-center">
                    <div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: colors.primary }}></div>
                    Search Activities
                  </span>
                </label>
                <input
                  type="text"
                  placeholder="Start typing activity name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg text-sm transition-colors"
                  style={{
                    backgroundColor: colors.muted,
                    color: colors.foreground,
                    border: `1px solid ${colors.border}`,
                    outline: 'none'
                  }}
                  onFocus={(e) => e.target.style.borderColor = colors.primary}
                  onBlur={(e) => e.target.style.borderColor = colors.border}
                />
              </div>

              {/* Single row with Year Selection and Sliders */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                {/* Year Selection */}
                <div>
                  <label className="block text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
                    <span className="flex items-center">
                      <div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: colors.primary }}></div>
                      Filter by Years (Max 3)
                    </span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {availableYears.map(year => (
                      <button
                        key={year}
                        onClick={() => {
                          setSelectedYears(prev => {
                            if (prev.includes(year)) {
                              // Remove year if already selected
                              return prev.filter(y => y !== year);
                            } else {
                              // Add year only if less than 3 selected
                              if (prev.length < 3) {
                                return [...prev, year];
                              } else {
                                // Show warning when trying to select 4th year
                                alert('You can select a maximum of 3 years to optimize database performance.');
                                return prev;
                              }
                            }
                          });
                        }}
                        className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                        style={{
                          backgroundColor: selectedYears.includes(year) ? colors.primary : colors.muted,
                          color: selectedYears.includes(year) ? 'white' : colors.foreground,
                          border: `1px solid ${selectedYears.includes(year) ? colors.primary : colors.border}`
                        }}
                      >
                        {year}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Elapsed Time Slider */}
                <div>
                  <label className="block text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
                    <span className="flex items-center">
                      <div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: colors.chart3 }}></div>
                      Min Elapsed Time: <span className="ml-1" style={{ color: colors.chart3 }}>{formatElapsedTime(minElapsedTime)}</span>
                    </span>
                  </label>
                  <div className="px-2">
                    <input
                      type="range"
                      min="0"
                      max="300"
                      step="15"
                      value={minElapsedTime}
                      onChange={(e) => setMinElapsedTime(Number(e.target.value))}
                      className="w-full h-3 rounded-lg appearance-none cursor-pointer slider-teal"
                      style={{ backgroundColor: colors.muted }}
                    />
                    <div className="flex justify-between text-xs mt-2" style={{ color: colors.mutedForeground }}>
                      <span>0:00</span>
                      <span>5:00</span>
                    </div>
                  </div>
                </div>

                {/* Normalised Power Slider */}
                <div>
                  <label className="block text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
                    <span className="flex items-center">
                      <div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: colors.accent }}></div>
                      Min Normalised Power: <span className="ml-1" style={{ color: colors.accent }}>{minNormalisedPower}W</span>
                    </span>
                  </label>
                  <div className="px-2">
                    <input
                      type="range"
                      min="0"
                      max="400"
                      step="10"
                      value={minNormalisedPower}
                      onChange={(e) => setMinNormalisedPower(Number(e.target.value))}
                      className="w-full h-3 rounded-lg appearance-none cursor-pointer slider-orange"
                      style={{ backgroundColor: colors.muted }}
                    />
                    <div className="flex justify-between text-xs mt-2" style={{ color: colors.mutedForeground }}>
                      <span>0W</span>
                      <span>400W</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Data Table */}
        <div className="rounded-xl shadow-sm overflow-hidden" style={{ 
          backgroundColor: colors.card, 
          border: `1px solid ${colors.border}` 
        }}>
          <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium" style={{ color: colors.foreground }}>
                Showing <span className="font-semibold" style={{ color: colors.primary }}>{filteredAndSortedActivities.length}</span> of <span className="font-semibold" style={{ color: colors.chart3 }}>{activities.length}</span> activities
              </p>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colors.primary }}></div>
                <span className="text-xs" style={{ color: colors.mutedForeground }}>Live Data</span>
              </div>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead style={{ backgroundColor: colors.muted }}>
                <tr>
                  {[
                    { key: 'dateTime', label: 'Date/Time', color: colors.mutedForeground },
                    { key: 'name', label: 'Activity', color: colors.mutedForeground },
                    { key: 'elapsedTime', label: 'Elapsed Time', color: colors.chart3 },
                    { key: 'distance', label: 'Distance (km)', color: colors.mutedForeground },
                    { key: 'avgSpeed', label: 'Avg Speed (km/h)', color: colors.mutedForeground },
                    { key: 'elevationGain', label: 'Elevation (m)', color: colors.mutedForeground },
                    { key: 'avgPower', label: 'Avg Power (W)', color: colors.mutedForeground },
                    { key: 'normalisedPower', label: 'Normalised Power (W)', color: colors.accent }
                  ].map(({ key, label, color }) => (
                    <th
                      key={key}
                      className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer hover:opacity-80 transition-opacity"
                      style={{ color }}
                      onClick={() => handleSort(key)}
                    >
                      <div className="flex items-center space-x-1">
                        <span>{label}</span>
                        <SortIcon column={key} />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody style={{ backgroundColor: colors.card }}>
                {filteredAndSortedActivities.map((activity, index) => (
                  <tr key={activity.id} 
                    className="transition-colors hover:opacity-80"
                    style={{ 
                      backgroundColor: index % 2 === 0 ? colors.card : colors.muted,
                      borderTop: index > 0 ? `1px solid ${colors.border}` : 'none'
                    }}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {new Date(activity.dateTime).toLocaleString('en-US', {
                        year: 'numeric',
                        month: 'numeric',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit'
                      })}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm activity-name" style={{ color: colors.foreground }} title={activity.name || 'Untitled'}>
                        <button onClick={() => window.location.href = `/activities/${activity.id}`} style={{background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', textAlign: 'left', width: '100%'}}>
                        {activity.name || 'Untitled'}
                        </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium" style={{ color: colors.chart3 }}>
                      {formatElapsedTime(activity.elapsedTime)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {activity.distance != null ? (activity.distance / 1000).toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {activity.avgSpeed != null ? activity.avgSpeed.toFixed(1) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {activity.elevationGain != null ? activity.elevationGain : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {activity.avgPower != null ? activity.avgPower : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold" style={{ color: colors.accent }}>
                      {activity.normalisedPower != null ? activity.normalisedPower : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <style jsx>{`
        .slider-teal::-webkit-slider-thumb {
          appearance: none;
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: ${colors.chart3};
          cursor: pointer;
          border: 2px solid ${colors.card};
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .slider-teal::-moz-range-thumb {
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: ${colors.chart3};
          cursor: pointer;
          border: 2px solid ${colors.card};
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .slider-orange::-webkit-slider-thumb {
          appearance: none;
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: ${colors.accent};
          cursor: pointer;
          border: 2px solid ${colors.card};
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .slider-orange::-moz-range-thumb {
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: ${colors.accent};
          cursor: pointer;
          border: 2px solid ${colors.card};
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .activity-name {
          max-width: 120px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        @media (min-width: 768px) {
          .activity-name {
            max-width: 200px;
          }
        }

        @media (min-width: 1024px) {
          .activity-name {
            max-width: 300px;
          }
        }
      `}</style>
    </div>
  );
};

const ActivitiesPage = () => {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'hsl(210, 10%, 15%)' }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p style={{ color: 'hsl(210, 25%, 96.5%)' }}>Loading activities...</p>
        </div>
      </div>
    }>
      <ActivitiesContent />
    </Suspense>
  );
};

export default ActivitiesPage;

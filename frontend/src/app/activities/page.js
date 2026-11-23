'use client';
import React, { useState, useMemo, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Navigation from '../../components/Navigation';
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Filter, TrendingUp, Activity, RefreshCw, User } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useAuth } from '../../contexts/AuthContext';
import { demoActivitiesData } from '../../data/demoActivities';

const PAGE_SIZE = 50;
const PRODUCTION_ACTIVITIES_API_URL = 'https://1m4c74owqj.execute-api.eu-west-2.amazonaws.com/Prod';

const ActivitiesContent = () => {
  const searchParams = useSearchParams();
  const { user, isAuthenticated, isDemoMode } = useAuth();
  const userEmail = user?.email;
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [olderError, setOlderError] = useState(false);
  const retryOlder = useRef(null);
  const [page, setPage] = useState(1);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [selectedYears, setSelectedYears] = useState(['2025', '2026']); // Default to recent years
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

  useEffect(() => {
    if (searchParams.get('refresh') !== 'true') return;

    const url = new URL(window.location.href);
    url.searchParams.delete('refresh');
    window.history.replaceState(null, '', url);
    setRefreshVersion(version => version + 1);
  }, [searchParams]);

  useEffect(() => {
    const demoEmail = process.env.NEXT_PUBLIC_DEMO_EMAIL;
    const useDemoData = isDemoMode || localStorage.getItem('demoMode') === 'true' ||
      (Boolean(demoEmail) && userEmail === demoEmail);
    const token = localStorage.getItem('authToken');

    setLoading(true);
    setError(null);
    setPage(1);
    setActivities([]);
    setLoadingOlder(false);
    setOlderError(false);
    retryOlder.current = null;

    // Auth initializes on mount. A profile update for the same email does
    // not require a second activity request.
    if (!useDemoData && (!isAuthenticated || !token)) {
      return;
    }

    if (useDemoData) {
      setActivities(selectedYears.length ? demoActivitiesData.filter(activity =>
        selectedYears.includes(String(new Date(activity.dateTime).getFullYear()))
      ) : demoActivitiesData);
      setLoading(false);
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_ACTIVITIES_API_URL ||
      (window.location.hostname === 'veloclicks-prod.vercel.app'
        ? PRODUCTION_ACTIVITIES_API_URL
        : process.env.NEXT_PUBLIC_API_URL);
    const controller = new AbortController();
    const isCurrent = () => !controller.signal.aborted && localStorage.getItem('authToken') === token;

    async function loadPages(cursor = null) {
      if (!isCurrent()) return;
      try {
        do {
          const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
          if (selectedYears.length) params.set('years', selectedYears.join(','));
          if (cursor) params.set('cursor', cursor);

          const response = await fetch(`${apiUrl}/strava/activities/?${params}`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: controller.signal,
          });
          if (!response.ok) throw new Error('Failed to fetch activities');

          const { activities: rows, next_cursor: nextCursor } = await response.json();
          if (!isCurrent()) return;
          const batch = rows.map(activity => ({
            id: activity.id,
            name: activity.name,
            dateTime: activity.start_date_local || activity.start_date,
            elapsedTime: Math.round((activity.elapsed_time || 0) / 60),
            distance: activity.distance || 0,
            avgSpeed: activity.average_speed || 0,
            elevationGain: activity.total_elevation_gain || 0,
            avgPower: activity.average_watts || 0,
            normalisedPower: activity.weighted_average_watts || 0,
          }));

          if (cursor) {
            setActivities(previous => [...previous, ...batch]);
          } else {
            setActivities(batch);
            setLoading(false);
          }
          cursor = nextCursor;
          setLoadingOlder(Boolean(cursor));
        } while (cursor);
      } catch (err) {
        if (!isCurrent()) return;
        if (cursor) {
          // Retain earlier batches and resume at the failed cursor on retry.
          const failedCursor = cursor;
          retryOlder.current = () => {
            retryOlder.current = null;
            setOlderError(false);
            setLoadingOlder(true);
            loadPages(failedCursor);
          };
          setLoadingOlder(false);
          setOlderError(true);
        } else {
          setError(err.message);
          setLoading(false);
        }
        console.error('Failed to fetch activities:', err);
      }
    }

    loadPages();
    return () => controller.abort();
  }, [selectedYears, isAuthenticated, isDemoMode, userEmail, refreshVersion]);

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

  // Dynamically generate available years from 2018 to current year
  const availableYears = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const startYear = 2018;
    const years = [];
    for (let year = startYear; year <= currentYear; year++) {
      years.push(year.toString());
    }
    return years;
  }, []);

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
    setPage(1);
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

  const matchCount = filteredAndSortedActivities.length;
  const pageCount = Math.max(1, Math.ceil(matchCount / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const visibleActivities = filteredAndSortedActivities.slice(pageStart, pageStart + PAGE_SIZE);
  const showResults = !loading && !error;

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
            <p role="status" className="text-sm mt-2" style={{ color: colors.primary }}>
              Loading activities...
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm mt-2" style={{ color: colors.accent }}>
              Error: {error}
            </p>
          )}
          {loadingOlder && (
            <p role="status" className="text-sm mt-2" style={{ color: colors.primary }}>
              Loading older activities. Search covers the rides loaded so far.
            </p>
          )}
          {olderError && (
            <div className="mt-2 flex items-center gap-2 text-sm" style={{ color: colors.accent }}>
              <p role="alert">Could not load older activities. Search covers the rides loaded so far.</p>
              <button type="button" className="underline" onClick={() => retryOlder.current?.()}>
                Retry
              </button>
            </div>
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
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setPage(1);
                  }}
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
                      onChange={(e) => {
                        setMinElapsedTime(Number(e.target.value));
                        setPage(1);
                      }}
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
                      onChange={(e) => {
                        setMinNormalisedPower(Number(e.target.value));
                        setPage(1);
                      }}
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

        {showResults && matchCount === 0 && (
          <p role="status" style={{ color: colors.mutedForeground }}>
            {loadingOlder || olderError ? 'No matches among the activities loaded so far.' :
              activities.length ? 'No activities match your filters.' : 'No activities found for this date range.'}
          </p>
        )}

        {showResults && matchCount > 0 && (
        <div className="rounded-xl shadow-sm overflow-hidden" style={{ 
          backgroundColor: colors.card, 
          border: `1px solid ${colors.border}` 
        }}>
          <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <p role="status" className="text-sm font-medium" style={{ color: colors.foreground }}>
                Showing {pageStart + 1}–{pageStart + visibleActivities.length} of {matchCount}
                {matchCount === activities.length ? ' activities' : ` matches (${activities.length} activities loaded)`}
              </p>
              {pageCount > 1 && (
                <nav aria-label="Top activity list pagination"
                  className="ml-4 flex shrink-0 items-center gap-1 text-sm font-medium"
                  style={{ color: colors.foreground }}>
                  <button type="button" aria-label="Previous page" disabled={currentPage === 1}
                    onClick={() => setPage(currentPage - 1)}
                    className="rounded p-1 hover:opacity-70 disabled:opacity-40">
                    <ChevronLeft aria-hidden="true" className="h-4 w-4" />
                  </button>
                  <span>{currentPage} of {pageCount}</span>
                  <button type="button" aria-label="Next page" disabled={currentPage === pageCount}
                    onClick={() => setPage(currentPage + 1)}
                    className="rounded p-1 hover:opacity-70 disabled:opacity-40">
                    <ChevronRight aria-hidden="true" className="h-4 w-4" />
                  </button>
                </nav>
              )}
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
                {visibleActivities.map((activity, index) => (
                  <tr key={activity.id} 
                    className="transition-colors hover:opacity-80"
                    style={{ 
                      backgroundColor: index % 2 === 0 ? colors.card : colors.muted,
                      borderTop: index > 0 ? `1px solid ${colors.border}` : 'none'
                    }}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: colors.mutedForeground }}>
                      {(() => {
                        const date = new Date(activity.dateTime);
                        const dateStr = date.toLocaleDateString('en-GB', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric'
                        });
                        const timeStr = date.toLocaleTimeString('en-GB', {
                          hour: '2-digit',
                          minute: '2-digit',
                          hour12: false
                        });
                        return `${dateStr} ${timeStr}`;
                      })()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm activity-name" title={activity.name || 'Untitled'}>
                        <button
                          onClick={() => window.location.href = `/activities/${activity.id}`}
                          className="hover:opacity-80 transition-opacity"
                          style={{
                            background: 'none',
                            border: 'none',
                            color: colors.primary,
                            cursor: 'pointer',
                            textAlign: 'left',
                            width: '100%',
                            fontWeight: '500',
                            textDecoration: 'underline'
                          }}
                        >
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
          {pageCount > 1 && (
            <nav aria-label="Activity list pagination" className="flex items-center justify-between gap-4 px-6 py-4 border-t"
              style={{ borderColor: colors.border, color: colors.foreground }}>
              <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}
                className="rounded px-3 py-2 disabled:opacity-50" style={{ backgroundColor: colors.muted }}>
                Previous
              </button>
              <span className="text-sm">Page {currentPage} of {pageCount}</span>
              <button type="button" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}
                className="rounded px-3 py-2 disabled:opacity-50" style={{ backgroundColor: colors.muted }}>
                Next
              </button>
            </nav>
          )}
        </div>
        )}
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

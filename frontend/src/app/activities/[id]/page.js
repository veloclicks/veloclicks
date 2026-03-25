'use client';
import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import Navigation from '../../../components/Navigation';
import { ArrowLeft, MapPin, Clock, Zap, TrendingUp, Heart, Thermometer, Eye, EyeOff, Activity, RefreshCw, User, Map, BarChart3 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAuth } from '../../../contexts/AuthContext';
import { getDemoActivityDetails } from '../../../data/demoActivityDetails';
import AIInsightsSection from '../../../components/AIInsightsSection';

// Dynamic import for Leaflet to avoid SSR issues
const MapContainer = dynamic(() => import('react-leaflet').then(mod => mod.MapContainer), {
  ssr: false,
  loading: () => <div>Loading map...</div>
});
const TileLayer = dynamic(() => import('react-leaflet').then(mod => mod.TileLayer), { ssr: false });
const Polyline = dynamic(() => import('react-leaflet').then(mod => mod.Polyline), { ssr: false });
const Marker = dynamic(() => import('react-leaflet').then(mod => mod.Marker), { ssr: false });
const CircleMarker = dynamic(() => import('react-leaflet').then(mod => mod.CircleMarker), { ssr: false });

const ActivityDetailPage = () => {
  // Import Leaflet CSS
  useEffect(() => {
    require('leaflet/dist/leaflet.css');
  }, []);
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const activityId = params.id;

  const [showMap, setShowMap] = useState(true);
  const [mapViewType, setMapViewType] = useState('simple'); // 'simple' or 'satellite'
  const [activity, setActivity] = useState(null);
  const [routeStreams, setRouteStreams] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredIndex, setHoveredIndex] = useState(null); // For map-elevation sync
  const [generatingPowerMetrics, setGeneratingPowerMetrics] = useState(false);

  // Fetch activity data from Flask API or use demo data
  useEffect(() => {
    const fetchActivity = async () => {
      try {
        setLoading(true);
        setError(null); // Clear any previous errors

        // Don't proceed if user data isn't available yet
        if (!user) {
          setLoading(false);
          return;
        }

        // Check if demo user - if so, use demo data
        if (user?.email === process.env.NEXT_PUBLIC_DEMO_EMAIL) {
          const demoData = getDemoActivityDetails(activityId);
          setActivity(demoData.activity);
          setRouteStreams(demoData.routeStreams);
          setLoading(false);
          return;
        }

        // For real users, fetch from API
        const token = localStorage.getItem('authToken');
        const authHeaders = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        };

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/activity/${activityId}`, {
          headers: authHeaders,
        });
        if (!response.ok) {
          throw new Error('Failed to fetch activity');
        }
        const data = await response.json();
        setActivity(data);

        // Fetch route streams for map and optimized elevation profile
        try {
          // Fetch basic streams for map (latlng only needed)
          const streamsResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/activity/${activityId}/streams?types=latlng`, {
            headers: authHeaders,
          });
          if (streamsResponse.ok) {
            const streamsData = await streamsResponse.json();
            setRouteStreams(streamsData);
          }

          // Fetch optimized elevation profile data
          const elevationResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/activity/${activityId}/elevation-profile`, {
            headers: authHeaders,
          });
          if (elevationResponse.ok) {
            const elevationData = await elevationResponse.json();
            setRouteStreams(prev => ({
              ...prev,
              elevationProfile: elevationData
            }));
          }
        } catch (streamsError) {
          console.warn('Failed to fetch route streams:', streamsError);
          // Don't set error - just means no GPS data available
        }
      } catch (err) {
        setError(err.message);
        console.error('Failed to fetch activity:', err);
      } finally {
        setLoading(false);
      }
    };

    if (activityId) {
      fetchActivity();
    }
  }, [activityId, user]);

  // Get route coordinates from Strava GPS data (must be before early returns)
  const routePoints = useMemo(() => {
    if (routeStreams?.latlng?.data) {
      return routeStreams.latlng.data.map(([lat, lng]) => ({ lat, lng }));
    }
    return [];
  }, [routeStreams]);

  // Use optimized elevation profile data from backend
  const elevationData = useMemo(() => {
    if (routeStreams?.elevationProfile?.profile_data) {
      return routeStreams.elevationProfile.profile_data;
    }
    return [];
  }, [routeStreams]);

  // Calculate map center and bounds
  const mapCenter = useMemo(() => {
    if (routePoints.length === 0) return [0, 0];
    const latSum = routePoints.reduce((sum, point) => sum + point.lat, 0);
    const lngSum = routePoints.reduce((sum, point) => sum + point.lng, 0);
    return [latSum / routePoints.length, lngSum / routePoints.length];
  }, [routePoints]);

  // Helper function to format duration for display
  const formatDuration = (seconds) => {
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    }
  };

  // Parse power curve and time in zones data (must be before early returns)
  const powerCurveData = useMemo(() => {
    if (!activity?.power_curve_data) return null;
    try {
      const parsed = JSON.parse(activity.power_curve_data);
      return Object.entries(parsed).map(([duration, watts]) => ({
        duration: parseInt(duration),
        durationLabel: formatDuration(parseInt(duration)),
        watts: parseFloat(watts)
      })).sort((a, b) => a.duration - b.duration);
    } catch (e) {
      console.error('Error parsing power curve data:', e);
      return null;
    }
  }, [activity]);

  const timeInZonesData = useMemo(() => {
    if (!activity?.time_in_zones) return null;
    try {
      const parsed = JSON.parse(activity.time_in_zones);
      return Object.entries(parsed).map(([zone, seconds]) => ({
        zone: zone.toUpperCase(),
        minutes: Math.round(seconds / 60),
        seconds: parseInt(seconds)
      })).filter(z => z.seconds > 0); // Only show zones with time
    } catch (e) {
      console.error('Error parsing time in zones data:', e);
      return null;
    }
  }, [activity]);

  const hasPowerMetrics = powerCurveData !== null || timeInZonesData !== null;

  // Calculate Y-axis ticks for power curve (evenly spaced in 25W increments)
  const powerCurveYTicks = useMemo(() => {
    if (!powerCurveData || powerCurveData.length === 0) return [];

    const minWatts = Math.min(...powerCurveData.map(d => d.watts));
    const maxWatts = Math.max(...powerCurveData.map(d => d.watts));

    // Round down to nearest 25 for min, round up to nearest 25 for max
    const minTick = Math.floor(minWatts / 25) * 25;
    const maxTick = Math.ceil(maxWatts / 25) * 25;

    // Generate ticks in 25W increments
    const ticks = [];
    for (let i = minTick; i <= maxTick; i += 25) {
      ticks.push(i);
    }

    return ticks;
  }, [powerCurveData]);

  // Calculate X-axis ticks for power curve (key time intervals)
  const powerCurveXTicks = useMemo(() => {
    if (!powerCurveData || powerCurveData.length === 0) return [];

    const maxDuration = Math.max(...powerCurveData.map(d => d.duration));
    const ticks = [];

    // Add key intervals based on max duration
    if (maxDuration >= 30) ticks.push(30); // 30s
    if (maxDuration >= 60) ticks.push(60); // 1m
    if (maxDuration >= 120) ticks.push(120); // 2m
    if (maxDuration >= 300) ticks.push(300); // 5m
    if (maxDuration >= 600) ticks.push(600); // 10m
    if (maxDuration >= 1200) ticks.push(1200); // 20m
    if (maxDuration >= 1800) ticks.push(1800); // 30m
    if (maxDuration >= 3600) ticks.push(3600); // 1h

    // Add hour marks if duration is longer than 1 hour
    if (maxDuration > 3600) {
      for (let h = 2; h <= Math.floor(maxDuration / 3600); h++) {
        ticks.push(h * 3600);
      }
    }

    return ticks;
  }, [powerCurveData]);


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

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="flex items-center justify-center h-64">
          <p style={{ color: colors.primary }}>Loading activity...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="flex items-center justify-center h-64">
          <p style={{ color: colors.accent }}>Error: {error}</p>
        </div>
      </div>
    );
  }

  // Show not found state
  if (!activity) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="flex items-center justify-center h-64">
          <p style={{ color: colors.mutedForeground }}>Activity not found</p>
        </div>
      </div>
    );
  }

  const formatTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  };


  const StatCard = ({ icon, label, value, unit, color = colors.foreground, size = 'normal' }) => (
    <div className="p-4 rounded-lg" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
      <div className="flex items-center space-x-3">
        <div className="p-2 rounded-lg" style={{ backgroundColor: colors.muted }}>
          {React.cloneElement(icon, { className: 'h-5 w-5', style: { color } })}
        </div>
        <div className="flex-1">
          <div className={`font-bold ${size === 'large' ? 'text-2xl' : 'text-xl'}`} style={{ color }}>
            {value}
            {unit && <span className="text-sm ml-1" style={{ color: colors.mutedForeground }}>{unit}</span>}
          </div>
          <div className="text-sm" style={{ color: colors.mutedForeground }}>{label}</div>
        </div>
      </div>
    </div>
  );

  // Create SVG path from route points
  const createSVGPath = (points) => {
    if (points.length === 0) return '';
    
    const minLat = Math.min(...points.map(p => p.lat));
    const maxLat = Math.max(...points.map(p => p.lat));
    const minLng = Math.min(...points.map(p => p.lng));
    const maxLng = Math.max(...points.map(p => p.lng));
    
    const width = 400;
    const height = 300;
    const padding = 20;
    
    const scaleX = (width - 2 * padding) / (maxLng - minLng);
    const scaleY = (height - 2 * padding) / (maxLat - minLat);
    
    const pathCommands = points.map((point, index) => {
      const x = padding + (point.lng - minLng) * scaleX;
      const y = height - padding - (point.lat - minLat) * scaleY;
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
    
    return pathCommands;
  };

  const svgPath = createSVGPath(routePoints);

  // Generate power metrics
  const handleGeneratePowerMetrics = async () => {
    try {
      setGeneratingPowerMetrics(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/activity/${activityId}/calculate-power-metrics`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to generate power metrics');
      }

      // Refresh activity data to show new metrics
      const activityResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/activity/${activityId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (activityResponse.ok) {
        const updatedActivity = await activityResponse.json();
        setActivity(updatedActivity);
      }
    } catch (err) {
      console.error('Error generating power metrics:', err);
      alert('Failed to generate power metrics. Please try again.');
    } finally {
      setGeneratingPowerMetrics(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      {/* Navigation */}
      < Navigation />

      {/* Page Header */}
      <div className="shadow-sm" style={{ backgroundColor: colors.card, borderBottom: `1px solid ${colors.border}` }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <button 
              className="flex items-center space-x-2 hover:opacity-80 transition-colors mr-6"
              style={{ color: colors.primary }}
              onClick={() => router.push('/activities')}
            >
              <ArrowLeft className="h-5 w-5" />
              <span>Back to Activities</span>
            </button>
            <div className="flex-1">
              <h1 className="text-2xl font-bold" style={{ color: colors.foreground }}>
                {activity.name || 'Untitled Activity'}
              </h1>
              <p className="text-sm" style={{ color: colors.mutedForeground }}>
                {activity.start_date_local ? new Date(activity.start_date_local).toLocaleDateString('en-US', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit'
                }) : 'Date not available'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-sm font-medium" style={{ 
                backgroundColor: colors.primary, 
                color: 'white' 
              }}>
                {activity.type || 'Activity'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Key Stats */}
          <div className="lg:col-span-1 space-y-6">
            {/* Primary Stats */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>Key Metrics</h3>
              
              <StatCard
                icon={<MapPin />}
                label="Distance"
                value={activity.distance ? (activity.distance / 1000).toFixed(1) : '-'}
                unit="km"
                color={colors.primary}
                size="large"
              />
              
              <StatCard
                icon={<Clock />}
                label="Elapsed Time"
                value={activity.elapsed_time ? formatTime(Math.round(activity.elapsed_time / 60)) : '-'}
                color={colors.chart3}
                size="large"
              />
              
              <StatCard
                icon={<TrendingUp />}
                label="Elevation Gain"
                value={activity.total_elevation_gain || '-'}
                unit="m"
                color={colors.accent}
              />
            </div>

            {/* Performance Stats */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>Performance</h3>
              
              <div className="grid grid-cols-2 gap-3">
                <StatCard
                  icon={<Zap />}
                  label="Avg Speed"
                  value={activity.average_speed ? activity.average_speed.toFixed(1) : '-'}
                  unit="km/h"
                  color={colors.primary}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Max Speed"
                  value={activity.max_speed ? activity.max_speed.toFixed(1) : '-'}
                  unit="km/h"
                  color={colors.accent}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Avg Power"
                  value={activity.average_watts || '-'}
                  unit="W"
                  color={colors.chart3}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Max Power"
                  value={activity.max_watts || '-'}
                  unit="W"
                  color={colors.accent}
                />
                
                <StatCard
                  icon={<Heart />}
                  label="Avg HR"
                  value={activity.average_heartrate || '-'}
                  unit="bpm"
                  color={colors.primary}
                />
                
                <StatCard
                  icon={<Heart />}
                  label="Max HR"
                  value={activity.max_heartrate || '-'}
                  unit="bpm"
                  color={colors.accent}
                />
              </div>
            </div>

            {/* Additional Info */}
            <div className="rounded-lg p-4" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>Additional Details</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Moving Time</span>
                  <span style={{ color: colors.foreground }}>{activity.moving_time ? formatTime(Math.round(activity.moving_time / 60)) : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Normalised Power</span>
                  <span style={{ color: colors.accent }}>{activity.weighted_average_watts ? activity.weighted_average_watts + 'W' : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>FTP at Activity Time</span>
                  <span style={{ color: colors.primary }}>{activity.ftp ? activity.ftp + ' W' : 'Unset'}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Avg Cadence</span>
                  <span style={{ color: colors.foreground }}>{activity.average_cadence ? activity.average_cadence + ' rpm' : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Calories</span>
                  <span style={{ color: colors.foreground }}>-</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Temperature</span>
                  <span style={{ color: colors.foreground }}>-</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Bike</span>
                  <span style={{ color: colors.foreground }}>-</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Map and Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Route Map */}
            <div className="rounded-lg" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <div className="p-4 border-b" style={{ borderColor: colors.border }}>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>Route Map</h3>
                  <div className="flex items-center space-x-2">
                    {showMap && (
                      <div className="flex items-center space-x-1 mr-2">
                        <button
                          onClick={() => setMapViewType('simple')}
                          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                            mapViewType === 'simple' ? 'opacity-100' : 'opacity-60 hover:opacity-80'
                          }`}
                          style={{
                            backgroundColor: mapViewType === 'simple' ? colors.primary : colors.muted,
                            color: mapViewType === 'simple' ? 'white' : colors.mutedForeground
                          }}
                        >
                          <BarChart3 className="h-3 w-3 mr-1 inline" />
                          Simple
                        </button>
                        <button
                          onClick={() => setMapViewType('satellite')}
                          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                            mapViewType === 'satellite' ? 'opacity-100' : 'opacity-60 hover:opacity-80'
                          }`}
                          style={{
                            backgroundColor: mapViewType === 'satellite' ? colors.primary : colors.muted,
                            color: mapViewType === 'satellite' ? 'white' : colors.mutedForeground
                          }}
                        >
                          <Map className="h-3 w-3 mr-1 inline" />
                          Satellite
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => setShowMap(!showMap)}
                      className="flex items-center space-x-2 px-3 py-1 rounded-lg transition-colors hover:opacity-80"
                      style={{ backgroundColor: colors.muted, color: colors.mutedForeground }}
                    >
                      {showMap ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      <span>{showMap ? 'Hide' : 'Show'} Map</span>
                    </button>
                  </div>
                </div>
              </div>
              
              {showMap && (
                <div className="p-4">
                  {routePoints.length === 0 ? (
                    <div className="w-full h-80 rounded-lg flex items-center justify-center" style={{ backgroundColor: colors.muted }}>
                      <p style={{ color: colors.mutedForeground }}>No GPS data available for this activity</p>
                    </div>
                  ) : mapViewType === 'simple' ? (
                    <>
                      <div className="w-full h-80 rounded-lg overflow-hidden" style={{ backgroundColor: colors.muted }}>
                        <svg width="100%" height="100%" viewBox="0 0 400 300">
                      {/* Background */}
                      <rect width="400" height="300" fill={colors.muted} />
                      
                      {/* Grid lines */}
                      <defs>
                        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                          <path d="M 20 0 L 0 0 0 20" fill="none" stroke={colors.border} strokeWidth="0.5" opacity="0.3"/>
                        </pattern>
                      </defs>
                      <rect width="400" height="300" fill="url(#grid)" />
                      
                      {/* Route path */}
                      <path
                        d={svgPath}
                        fill="none"
                        stroke={colors.primary}
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      
                      {/* Start point */}
                      {routePoints.length > 0 && (() => {
                        const minLng = Math.min(...routePoints.map(p => p.lng));
                        const maxLng = Math.max(...routePoints.map(p => p.lng));
                        const minLat = Math.min(...routePoints.map(p => p.lat));
                        const maxLat = Math.max(...routePoints.map(p => p.lat));
                        const lngRange = maxLng - minLng || 1; // Avoid division by zero
                        const latRange = maxLat - minLat || 1; // Avoid division by zero
                        const cx = 20 + (routePoints[0].lng - minLng) * 360 / lngRange;
                        const cy = 280 - (routePoints[0].lat - minLat) * 260 / latRange;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r="6"
                            fill={colors.chart3}
                            stroke="white"
                            strokeWidth="2"
                          />
                        );
                      })()}

                      {/* End point */}
                      {routePoints.length > 0 && (() => {
                        const minLng = Math.min(...routePoints.map(p => p.lng));
                        const maxLng = Math.max(...routePoints.map(p => p.lng));
                        const minLat = Math.min(...routePoints.map(p => p.lat));
                        const maxLat = Math.max(...routePoints.map(p => p.lat));
                        const lngRange = maxLng - minLng || 1; // Avoid division by zero
                        const latRange = maxLat - minLat || 1; // Avoid division by zero
                        const cx = 20 + (routePoints[routePoints.length - 1].lng - minLng) * 360 / lngRange;
                        const cy = 280 - (routePoints[routePoints.length - 1].lat - minLat) * 260 / latRange;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r="6"
                            fill={colors.accent}
                            stroke="white"
                            strokeWidth="2"
                          />
                        );
                      })()}
                      
                      {/* Hover indicator - synchronized with elevation chart */}
                      {hoveredIndex !== null && elevationData[hoveredIndex] && routePoints.length > 0 && (() => {
                        const minLng = Math.min(...routePoints.map(p => p.lng));
                        const maxLng = Math.max(...routePoints.map(p => p.lng));
                        const minLat = Math.min(...routePoints.map(p => p.lat));
                        const maxLat = Math.max(...routePoints.map(p => p.lat));
                        const lngRange = maxLng - minLng || 1; // Avoid division by zero
                        const latRange = maxLat - minLat || 1; // Avoid division by zero
                        const cx = 20 + (elevationData[hoveredIndex].lng - minLng) * 360 / lngRange;
                        const cy = 280 - (elevationData[hoveredIndex].lat - minLat) * 260 / latRange;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r="8"
                            fill={colors.accent}
                            stroke="white"
                            strokeWidth="3"
                            opacity="0.9"
                          >
                            <animate attributeName="r" values="8;12;8" dur="1.5s" repeatCount="indefinite" />
                          </circle>
                        );
                      })()}

                      {/* Legend */}
                      <g>
                        <circle cx="30" cy="30" r="4" fill={colors.chart3} stroke="white" strokeWidth="1"/>
                        <text x="40" y="35" fill={colors.foreground} fontSize="12">Start</text>
                        <circle cx="30" cy="50" r="4" fill={colors.accent} stroke="white" strokeWidth="1"/>
                        <text x="40" y="55" fill={colors.foreground} fontSize="12">Finish</text>
                      </g>
                        </svg>
                      </div>
                      <p className="text-xs mt-2 text-center" style={{ color: colors.mutedForeground }}>
                        Interactive route map • Green: Start • Orange: Finish
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="w-full h-80 rounded-lg overflow-hidden" style={{ backgroundColor: colors.muted }}>
                        <MapContainer
                          center={mapCenter}
                          zoom={13}
                          style={{ height: '100%', width: '100%' }}
                        >
                          <TileLayer
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                          />
                          <Polyline
                            positions={routePoints.map(point => [point.lat, point.lng])}
                            color={colors.primary}
                            weight={3}
                            opacity={0.8}
                          />
                          {routePoints.length > 0 && (
                            <Marker position={[routePoints[0].lat, routePoints[0].lng]} />
                          )}
                          {routePoints.length > 1 && (
                            <Marker position={[routePoints[routePoints.length - 1].lat, routePoints[routePoints.length - 1].lng]} />
                          )}
                          {/* Hover indicator - shows position synchronized with elevation chart */}
                          {hoveredIndex !== null && elevationData[hoveredIndex] && (
                            <CircleMarker
                              center={[elevationData[hoveredIndex].lat, elevationData[hoveredIndex].lng]}
                              radius={8}
                              pathOptions={{
                                color: colors.accent,
                                fillColor: colors.accent,
                                fillOpacity: 0.8,
                                weight: 3
                              }}
                            />
                          )}
                        </MapContainer>
                      </div>
                      <p className="text-xs mt-2 text-center" style={{ color: colors.mutedForeground }}>
                        Satellite map view • Route overlaid on OpenStreetMap
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Elevation Profile */}
            {elevationData.length > 0 && (
              <div className="mt-6 rounded-xl shadow-sm" style={{
                backgroundColor: colors.card,
                border: `1px solid ${colors.border}`
              }}>
                <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>
                      Elevation Profile
                    </h3>
                    <BarChart3 className="h-5 w-5" style={{ color: colors.primary }} />
                  </div>
                </div>

                <div className="p-6">
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart
                      data={elevationData}
                      onMouseMove={(data) => {
                        if (data && data.activeTooltipIndex !== undefined) {
                          setHoveredIndex(data.activeTooltipIndex);
                        }
                      }}
                      onMouseLeave={() => setHoveredIndex(null)}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
                      <XAxis
                        dataKey="distance"
                        stroke={colors.mutedForeground}
                        label={{ value: 'Distance (km)', position: 'insideBottom', offset: -5, style: { fill: colors.mutedForeground } }}
                      />
                      <YAxis
                        stroke={colors.mutedForeground}
                        label={{ value: 'Elevation (m)', angle: -90, position: 'insideLeft', style: { fill: colors.mutedForeground } }}
                      />
                      <Tooltip content={() => null} cursor={{ stroke: colors.accent, strokeWidth: 1 }} />
                      <Area
                        type="monotone"
                        dataKey="elevation"
                        stroke={colors.primary}
                        fill={colors.primary}
                        fillOpacity={0.3}
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>

                  {/* Hover Data Display */}
                  <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: colors.muted, border: `1px solid ${colors.border}`, minHeight: '60px' }}>
                    {hoveredIndex !== null && elevationData[hoveredIndex] ? (
                      <div className="grid grid-cols-5 gap-3 text-xs">
                        <div>
                          <div style={{ color: colors.mutedForeground }}>Distance</div>
                          <div className="font-semibold" style={{ color: colors.foreground }}>
                            {elevationData[hoveredIndex].distance}km
                          </div>
                        </div>
                        <div>
                          <div style={{ color: colors.mutedForeground }}>Elevation</div>
                          <div className="font-semibold" style={{ color: colors.primary }}>
                            {elevationData[hoveredIndex].elevation}m
                          </div>
                        </div>
                        {elevationData[hoveredIndex].gradient !== undefined && (
                          <div>
                            <div style={{ color: colors.mutedForeground }}>Gradient</div>
                            <div className="font-semibold" style={{ color: '#fbbf24' }}>
                              {elevationData[hoveredIndex].gradient}%
                            </div>
                          </div>
                        )}
                        {elevationData[hoveredIndex].power && (
                          <div>
                            <div style={{ color: colors.mutedForeground }}>Power</div>
                            <div className="font-semibold" style={{ color: colors.chart3 }}>
                              {elevationData[hoveredIndex].power}W
                            </div>
                          </div>
                        )}
                        {elevationData[hoveredIndex].heartrate && (
                          <div>
                            <div style={{ color: colors.mutedForeground }}>Heart Rate</div>
                            <div className="font-semibold" style={{ color: colors.accent }}>
                              {elevationData[hoveredIndex].heartrate} bpm
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-center" style={{ color: colors.mutedForeground, paddingTop: '8px' }}>
                        Hover over the chart to see details
                      </div>
                    )}
                  </div>

                  <div className="mt-4 grid grid-cols-3 gap-4" style={{ display: 'none' }}>
                    <div className="text-center">
                      <div className="text-sm" style={{ color: colors.mutedForeground }}>Min Elevation</div>
                      <div className="text-lg font-semibold" style={{ color: colors.foreground }}>
                        {elevationData.length > 0 ? Math.min(...elevationData.map(d => d.elevation)).toFixed(0) : '-'}m
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm" style={{ color: colors.mutedForeground }}>Max Elevation</div>
                      <div className="text-lg font-semibold" style={{ color: colors.foreground }}>
                        {elevationData.length > 0 ? Math.max(...elevationData.map(d => d.elevation)).toFixed(0) : '-'}m
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm" style={{ color: colors.mutedForeground }}>Total Distance</div>
                      <div className="text-lg font-semibold" style={{ color: colors.foreground }}>
                        {elevationData.length > 0 ? elevationData[elevationData.length - 1].distance.toFixed(1) : '-'}km
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* AI Insights Section */}
            <AIInsightsSection
              activityId={activityId}
              isPremiumUser={user?.membership_type === 'PREMIUM_TIER'}
              colors={colors}
            />

            {/* Power Insights Section */}
            {activity.average_watts && (
              <div className="mt-6 rounded-xl shadow-sm" style={{
                backgroundColor: colors.card,
                border: `1px solid ${colors.border}`
              }}>
                <div className="px-6 py-4 border-b" style={{ borderColor: colors.border }}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>
                      Power Insights
                    </h3>
                    <Zap className="h-5 w-5" style={{ color: colors.accent }} />
                  </div>
                </div>

                <div className="p-6">
                  {!hasPowerMetrics ? (
                    <div className="text-center py-8">
                      <p className="text-sm mb-4" style={{ color: colors.mutedForeground }}>
                        Generate detailed power analysis including power curve and time in zones
                      </p>
                      <button
                        onClick={handleGeneratePowerMetrics}
                        disabled={generatingPowerMetrics}
                        className="px-6 py-3 rounded-lg font-medium transition-colors hover:opacity-90 disabled:opacity-50"
                        style={{ backgroundColor: colors.accent, color: 'white' }}
                      >
                        {generatingPowerMetrics ? (
                          <span className="flex items-center space-x-2">
                            <RefreshCw className="h-4 w-4 animate-spin" />
                            <span>Generating...</span>
                          </span>
                        ) : (
                          'Generate Power Insights'
                        )}
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Power Curve */}
                      {powerCurveData && (
                        <div>
                          <h4 className="text-md font-semibold mb-4" style={{ color: colors.foreground }}>
                            Power Curve
                          </h4>
                          <ResponsiveContainer width="100%" height={300}>
                            <AreaChart data={powerCurveData}>
                              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
                              <XAxis
                                dataKey="duration"
                                type="number"
                                domain={['dataMin', 'dataMax']}
                                ticks={powerCurveXTicks}
                                tickFormatter={(value) => formatDuration(value)}
                                stroke={colors.mutedForeground}
                                label={{ value: 'Duration', position: 'insideBottom', offset: -5, style: { fill: colors.mutedForeground } }}
                              />
                              <YAxis
                                domain={[powerCurveYTicks[0], powerCurveYTicks[powerCurveYTicks.length - 1]]}
                                ticks={powerCurveYTicks}
                                stroke={colors.mutedForeground}
                                label={{ value: 'Power (W)', angle: -90, position: 'insideLeft', style: { fill: colors.mutedForeground } }}
                              />
                              <Tooltip
                                contentStyle={{
                                  backgroundColor: colors.card,
                                  border: `1px solid ${colors.border}`,
                                  borderRadius: '8px',
                                  color: colors.foreground
                                }}
                                content={({ active, payload }) => {
                                  if (active && payload && payload.length) {
                                    const data = payload[0].payload;
                                    return (
                                      <div style={{
                                        backgroundColor: colors.card,
                                        border: `1px solid ${colors.border}`,
                                        borderRadius: '8px',
                                        padding: '8px 12px',
                                        color: colors.foreground
                                      }}>
                                        <p style={{ margin: '0 0 4px 0', fontWeight: 'bold' }}>
                                          Duration: {data.durationLabel}
                                        </p>
                                        <p style={{ margin: '2px 0', color: colors.accent }}>
                                          Max Avg Power: {data.watts.toFixed(0)}W
                                        </p>
                                      </div>
                                    );
                                  }
                                  return null;
                                }}
                              />
                              <Area
                                type="monotone"
                                dataKey="watts"
                                stroke={colors.accent}
                                fill={colors.accent}
                                fillOpacity={0.3}
                                strokeWidth={2}
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                          <p className="text-xs mt-2 text-center" style={{ color: colors.mutedForeground }}>
                            Maximum average power sustained for different durations
                          </p>

                          {/* Key Power Metrics Table */}
                          <div className="mt-6">
                            <h5 className="text-sm font-semibold mb-3" style={{ color: colors.foreground }}>
                              Key Power Metrics
                            </h5>
                            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                              {[
                                { duration: 5, label: '5s' },
                                { duration: 10, label: '10s' },
                                { duration: 15, label: '15s' },
                                { duration: 60, label: '1min' },
                                { duration: 300, label: '5min' },
                                { duration: 1200, label: '20min' },
                                { duration: 3600, label: '60min' }
                              ].map(({ duration, label }) => {
                                // Find the exact duration or the closest one
                                const dataPoint = powerCurveData.find(d => d.duration === duration) ||
                                                 powerCurveData.reduce((closest, current) => {
                                                   if (current.duration > duration) return closest;
                                                   return !closest || Math.abs(current.duration - duration) < Math.abs(closest.duration - duration)
                                                     ? current
                                                     : closest;
                                                 }, null);

                                return (
                                  <div
                                    key={duration}
                                    className="p-3 rounded-lg text-center"
                                    style={{
                                      backgroundColor: colors.muted,
                                      border: `1px solid ${colors.border}`
                                    }}
                                  >
                                    <div className="text-xs font-medium mb-1" style={{ color: colors.mutedForeground }}>
                                      {label}
                                    </div>
                                    <div className="text-xl font-bold" style={{ color: colors.accent }}>
                                      {dataPoint ? dataPoint.watts.toFixed(0) : '-'}
                                    </div>
                                    <div className="text-xs" style={{ color: colors.mutedForeground }}>
                                      watts
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Time in Zones */}
                      {timeInZonesData && (
                        <div className="mt-6">
                          <h4 className="text-md font-semibold mb-4" style={{ color: colors.foreground }}>
                            Time in Power Zones
                          </h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {timeInZonesData.map((zone, index) => (
                              <div
                                key={zone.zone}
                                className="p-4 rounded-lg text-center"
                                style={{
                                  backgroundColor: colors.muted,
                                  border: `1px solid ${colors.border}`
                                }}
                              >
                                <div className="text-sm font-medium mb-1" style={{ color: colors.mutedForeground }}>
                                  {zone.zone}
                                </div>
                                <div className="text-2xl font-bold" style={{ color: colors.accent }}>
                                  {zone.minutes}
                                </div>
                                <div className="text-xs" style={{ color: colors.mutedForeground }}>
                                  minutes
                                </div>
                              </div>
                            ))}
                          </div>
                          <p className="text-xs mt-4 text-center" style={{ color: colors.mutedForeground }}>
                            Based on FTP at activity time: {activity.ftp ? `${activity.ftp}W` : 'Not set'}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}


          </div>
        </div>
      </div>
    </div>
  );
};

export default ActivityDetailPage;

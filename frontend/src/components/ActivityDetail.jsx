'use client';
import React, { useState } from 'react';
import { ArrowLeft, MapPin, Clock, Zap, TrendingUp, Heart, Thermometer, Eye, EyeOff, Activity, RefreshCw, User } from 'lucide-react';

const ActivityDetailPage = () => {
  const [showMap, setShowMap] = useState(true);
  
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

  // Sample activity data
  const activity = {
    id: 1,
    title: 'Morning Training Ride',
    date: '2024-03-15',
    time: '08:30 AM',
    type: 'Ride',
    distance: 42.5,
    elapsedTime: 125, // minutes
    movingTime: 118, // minutes
    elevation: 450,
    avgSpeed: 28.3,
    maxSpeed: 52.1,
    avgPower: 245,
    maxPower: 687,
    normalisedPower: 268,
    avgHeartRate: 152,
    maxHeartRate: 178,
    avgCadence: 87,
    maxCadence: 112,
    calories: 892,
    temperature: 12, // Celsius
    description: 'Great morning ride through the hills. Felt strong on the climbs and maintained good power throughout.',
    achievements: ['Personal Record on Hillside Climb', 'New monthly distance record'],
    weatherConditions: 'Partly Cloudy, 12°C',
    bike: 'Trek Domane SL7'
  };

  const formatTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
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

  // Mock route coordinates for the map
  const generateMockRoute = () => {
    const points = [];
    const centerLat = 51.5074;
    const centerLng = -0.1278;
    
    for (let i = 0; i < 50; i++) {
      const angle = (i / 50) * Math.PI * 4; // Multiple loops
      const radius = 0.01 + (i / 100) * 0.02;
      points.push({
        lat: centerLat + Math.sin(angle) * radius,
        lng: centerLng + Math.cos(angle) * radius
      });
    }
    return points;
  };

  const routePoints = generateMockRoute();

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

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      {/* Navigation */}
      <div className="shadow-lg" style={{ backgroundColor: colors.card, borderBottom: `1px solid ${colors.border}` }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: colors.primary }}>
                  <Activity className="h-5 w-5 text-white" />
                </div>
                <span className="text-xl font-bold" style={{ color: colors.foreground }}>Veloclicks</span>
              </div>
              
              <nav className="flex space-x-6">
                <button 
                  className="px-3 py-2 rounded-lg text-sm font-medium"
                  style={{ 
                    backgroundColor: colors.primary, 
                    color: 'white'
                  }}
                  onClick={() => alert('Navigate to Activities')}
                >
                  Activities
                </button>
                
                <button 
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80 flex items-center space-x-2"
                  style={{ color: colors.mutedForeground }}
                  onClick={() => alert('Navigate to Activity Sync')}
                >
                  <RefreshCw className="h-4 w-4" />
                  <span>Sync</span>
                </button>
                
                <button 
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                  style={{ color: colors.mutedForeground }}
                  onClick={() => alert('Navigate to Visualizations')}
                >
                  Visualizations
                </button>
                
                <button 
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                  style={{ color: colors.mutedForeground }}
                  onClick={() => alert('Navigate to Profile')}
                >
                  Profile
                </button>
              </nav>
            </div>
            
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: colors.muted }}>
                <User className="h-5 w-5" style={{ color: colors.foreground }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Page Header */}
      <div className="shadow-sm" style={{ backgroundColor: colors.card, borderBottom: `1px solid ${colors.border}` }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center py-4">
            <button 
              className="flex items-center space-x-2 hover:opacity-80 transition-colors mr-6"
              style={{ color: colors.primary }}
              onClick={() => alert('Navigate back to activities list')}
            >
              <ArrowLeft className="h-5 w-5" />
              <span>Back to Activities</span>
            </button>
            <div className="flex-1">
              <h1 className="text-2xl font-bold" style={{ color: colors.foreground }}>
                {activity.title}
              </h1>
              <p className="text-sm" style={{ color: colors.mutedForeground }}>
                {formatDate(activity.date)} at {activity.time}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-sm font-medium" style={{ 
                backgroundColor: colors.primary, 
                color: 'white' 
              }}>
                {activity.type}
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
                value={activity.distance.toFixed(1)}
                unit="km"
                color={colors.primary}
                size="large"
              />
              
              <StatCard
                icon={<Clock />}
                label="Elapsed Time"
                value={formatTime(activity.elapsedTime)}
                color={colors.chart3}
                size="large"
              />
              
              <StatCard
                icon={<TrendingUp />}
                label="Elevation Gain"
                value={activity.elevation}
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
                  value={activity.avgSpeed.toFixed(1)}
                  unit="km/h"
                  color={colors.primary}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Max Speed"
                  value={activity.maxSpeed.toFixed(1)}
                  unit="km/h"
                  color={colors.accent}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Avg Power"
                  value={activity.avgPower}
                  unit="W"
                  color={colors.chart3}
                />
                
                <StatCard
                  icon={<Zap />}
                  label="Max Power"
                  value={activity.maxPower}
                  unit="W"
                  color={colors.accent}
                />
                
                <StatCard
                  icon={<Heart />}
                  label="Avg HR"
                  value={activity.avgHeartRate}
                  unit="bpm"
                  color={colors.primary}
                />
                
                <StatCard
                  icon={<Heart />}
                  label="Max HR"
                  value={activity.maxHeartRate}
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
                  <span style={{ color: colors.foreground }}>{formatTime(activity.movingTime)}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Normalised Power</span>
                  <span style={{ color: colors.accent }}>{activity.normalisedPower}W</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Avg Cadence</span>
                  <span style={{ color: colors.foreground }}>{activity.avgCadence} rpm</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Calories</span>
                  <span style={{ color: colors.foreground }}>{activity.calories} kcal</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Temperature</span>
                  <span style={{ color: colors.foreground }}>{activity.temperature}°C</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: colors.mutedForeground }}>Bike</span>
                  <span style={{ color: colors.foreground }}>{activity.bike}</span>
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
              
              {showMap && (
                <div className="p-4">
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
                      {routePoints.length > 0 && (
                        <circle
                          cx={20 + (routePoints[0].lng - Math.min(...routePoints.map(p => p.lng))) * 360 / (Math.max(...routePoints.map(p => p.lng)) - Math.min(...routePoints.map(p => p.lng)))}
                          cy={280 - (routePoints[0].lat - Math.min(...routePoints.map(p => p.lat))) * 260 / (Math.max(...routePoints.map(p => p.lat)) - Math.min(...routePoints.map(p => p.lat)))}
                          r="6"
                          fill={colors.chart3}
                          stroke="white"
                          strokeWidth="2"
                        />
                      )}
                      
                      {/* End point */}
                      {routePoints.length > 0 && (
                        <circle
                          cx={20 + (routePoints[routePoints.length - 1].lng - Math.min(...routePoints.map(p => p.lng))) * 360 / (Math.max(...routePoints.map(p => p.lng)) - Math.min(...routePoints.map(p => p.lng)))}
                          cy={280 - (routePoints[routePoints.length - 1].lat - Math.min(...routePoints.map(p => p.lat))) * 260 / (Math.max(...routePoints.map(p => p.lat)) - Math.min(...routePoints.map(p => p.lat)))}
                          r="6"
                          fill={colors.accent}
                          stroke="white"
                          strokeWidth="2"
                        />
                      )}
                      
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
                </div>
              )}
            </div>

            {/* Activity Description */}
            <div className="rounded-lg p-4" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>Activity Notes</h3>
              <p className="text-sm leading-relaxed" style={{ color: colors.mutedForeground }}>
                {activity.description}
              </p>
            </div>

            {/* Achievements */}
            <div className="rounded-lg p-4" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>Achievements</h3>
              <div className="space-y-2">
                {activity.achievements.map((achievement, index) => (
                  <div key={index} className="flex items-center space-x-3 p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                    <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: colors.accent }}>
                      <TrendingUp className="h-4 w-4 text-white" />
                    </div>
                    <span style={{ color: colors.foreground }}>{achievement}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Weather & Equipment */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg p-4" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
                <h4 className="font-semibold mb-2" style={{ color: colors.foreground }}>Weather Conditions</h4>
                <div className="flex items-center space-x-2">
                  <Thermometer className="h-4 w-4" style={{ color: colors.primary }} />
                  <span className="text-sm" style={{ color: colors.mutedForeground }}>
                    {activity.weatherConditions}
                  </span>
                </div>
              </div>

              <div className="rounded-lg p-4" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
                <h4 className="font-semibold mb-2" style={{ color: colors.foreground }}>Equipment</h4>
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: colors.chart3 }}></div>
                  <span className="text-sm" style={{ color: colors.mutedForeground }}>
                    {activity.bike}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ActivityDetailPage;

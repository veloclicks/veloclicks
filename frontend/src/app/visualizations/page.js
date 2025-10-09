'use client';
import React, { useState, useMemo, useEffect } from 'react';
import Navigation from '../../components/Navigation';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Calendar, TrendingUp, RotateCcw } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const VisualizationsPage = () => {
  const [selectedYears, setSelectedYears] = useState(['2023', '2024', '2025']);
  const [activityData, setActivityData] = useState([]);
  const { isAuthenticated, user } = useAuth();
  
  // Dark theme colors matching your palette
  const colors = {
    background: 'hsl(210, 10%, 15%)',
    card: 'hsl(210, 10%, 20%)',
    foreground: 'hsl(210, 25%, 96.5%)',
    primary: 'hsl(207, 44%, 49%)',
    accent: 'hsl(16, 100%, 66%)',
    chart3: 'hsl(173, 58%, 39%)',
    chart4: 'hsl(43, 74%, 66%)',
    chart5: 'hsl(27, 87%, 67%)',
    muted: 'hsl(210, 10%, 25%)',
    mutedForeground: 'hsl(210, 15%, 65%)',
    border: 'hsl(210, 10%, 30%)',
  };

  // Demo activity data across multiple years
  const demoActivityData = [
    // 2020 data
    { year: 2020, month: 'Jan', hours: 15.5 },
    { year: 2020, month: 'Feb', hours: 18.2 },
    { year: 2020, month: 'Mar', hours: 22.7 },
    { year: 2020, month: 'Apr', hours: 28.1 },
    { year: 2020, month: 'May', hours: 31.8 },
    { year: 2020, month: 'Jun', hours: 35.2 },
    { year: 2020, month: 'Jul', hours: 38.7 },
    { year: 2020, month: 'Aug', hours: 36.4 },
    { year: 2020, month: 'Sep', hours: 29.8 },
    { year: 2020, month: 'Oct', hours: 24.6 },
    { year: 2020, month: 'Nov', hours: 19.3 },
    { year: 2020, month: 'Dec', hours: 16.1 },
    // 2021 data
    { year: 2021, month: 'Jan', hours: 17.2 },
    { year: 2021, month: 'Feb', hours: 20.1 },
    { year: 2021, month: 'Mar', hours: 25.4 },
    { year: 2021, month: 'Apr', hours: 32.7 },
    { year: 2021, month: 'May', hours: 35.9 },
    { year: 2021, month: 'Jun', hours: 38.8 },
    { year: 2021, month: 'Jul', hours: 42.1 },
    { year: 2021, month: 'Aug', hours: 39.6 },
    { year: 2021, month: 'Sep', hours: 33.2 },
    { year: 2021, month: 'Oct', hours: 27.8 },
    { year: 2021, month: 'Nov', hours: 21.5 },
    { year: 2021, month: 'Dec', hours: 18.7 },
    // 2022 data
    { year: 2022, month: 'Jan', hours: 19.8 },
    { year: 2022, month: 'Feb', hours: 23.4 },
    { year: 2022, month: 'Mar', hours: 28.9 },
    { year: 2022, month: 'Apr', hours: 35.2 },
    { year: 2022, month: 'May', hours: 38.7 },
    { year: 2022, month: 'Jun', hours: 41.3 },
    { year: 2022, month: 'Jul', hours: 44.8 },
    { year: 2022, month: 'Aug', hours: 42.1 },
    { year: 2022, month: 'Sep', hours: 35.6 },
    { year: 2022, month: 'Oct', hours: 30.2 },
    { year: 2022, month: 'Nov', hours: 24.8 },
    { year: 2022, month: 'Dec', hours: 21.3 },
    // 2023 data
    { year: 2023, month: 'Jan', hours: 22.1 },
    { year: 2023, month: 'Feb', hours: 25.7 },
    { year: 2023, month: 'Mar', hours: 31.2 },
    { year: 2023, month: 'Apr', hours: 37.8 },
    { year: 2023, month: 'May', hours: 41.5 },
    { year: 2023, month: 'Jun', hours: 43.9 },
    { year: 2023, month: 'Jul', hours: 47.2 },
    { year: 2023, month: 'Aug', hours: 44.6 },
    { year: 2023, month: 'Sep', hours: 38.1 },
    { year: 2023, month: 'Oct', hours: 32.7 },
    { year: 2023, month: 'Nov', hours: 27.4 },
    { year: 2023, month: 'Dec', hours: 23.8 },
    // 2024 data
    { year: 2024, month: 'Jan', hours: 24.5 },
    { year: 2024, month: 'Feb', hours: 28.3 },
    { year: 2024, month: 'Mar', hours: 33.8 },
    { year: 2024, month: 'Apr', hours: 40.1 },
    { year: 2024, month: 'May', hours: 43.7 },
    { year: 2024, month: 'Jun', hours: 46.2 },
    { year: 2024, month: 'Jul', hours: 49.8 },
    { year: 2024, month: 'Aug', hours: 47.1 },
    { year: 2024, month: 'Sep', hours: 40.5 },
    { year: 2024, month: 'Oct', hours: 35.3 },
    { year: 2024, month: 'Nov', hours: 29.6 },
    { year: 2024, month: 'Dec', hours: 26.2 },
    // 2025 data (partial year)
    { year: 2025, month: 'Jan', hours: 26.8 },
    { year: 2025, month: 'Feb', hours: 30.1 },
    { year: 2025, month: 'Mar', hours: 35.4 },
    { year: 2025, month: 'Apr', hours: 42.3 },
    { year: 2025, month: 'May', hours: 45.9 },
    { year: 2025, month: 'Jun', hours: 48.7 },
    { year: 2025, month: 'Jul', hours: 52.1 },
    { year: 2025, month: 'Aug', hours: 49.4 },
    { year: 2025, month: 'Sep', hours: 42.8 },
    { year: 2025, month: 'Oct', hours: 0 }, // Future months
    { year: 2025, month: 'Nov', hours: 0 },
    { year: 2025, month: 'Dec', hours: 0 },
  ];

  const availableYears = ['2020', '2021', '2022', '2023', '2024', '2025'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // Get the data source based on user type - simple logic
  const dataSource = (user?.email === process.env.NEXT_PUBLIC_DEMO_EMAIL) ? demoActivityData : activityData;

  // Transform data for the chart
  const chartData = useMemo(() => {
    return months.map(month => {
      const monthData = { month };

      selectedYears.forEach(year => {
        const dataPoint = dataSource.find(d => d.year.toString() === year && d.month === month);
        monthData[year] = dataPoint ? dataPoint.hours : 0;
      });

      return monthData;
    });
  }, [selectedYears, dataSource]);

  // Get colors for each year
  const getYearColor = (yearIndex) => {
    const yearColors = [colors.primary, colors.chart3, colors.accent, colors.chart4, colors.chart5];
    return yearColors[yearIndex % yearColors.length];
  };

  // Calculate totals for each year
  const yearTotals = useMemo(() => {
    return selectedYears.map(year => {
      const total = dataSource
        .filter(d => d.year.toString() === year)
        .reduce((sum, d) => sum + d.hours, 0);
      return { year, total };
    }).sort((a, b) => b.total - a.total);
  }, [selectedYears, dataSource]);

  const handleYearToggle = (year) => {
    if (selectedYears.includes(year)) {
      if (selectedYears.length > 1) {
        setSelectedYears(prev => prev.filter(y => y !== year));
      }
    } else {
      if (selectedYears.length < 5) {
        setSelectedYears(prev => [...prev, year].sort());
      }
    }
  };

  // Fetch and aggregate user activities into monthly training hours
  const fetchRealActivityData = async () => {
    if (!isAuthenticated) return;

    try {
      const token = localStorage.getItem('authToken');
      if (!token) return;

      // Get activities for all years from 2020 to current year
      const currentYear = new Date().getFullYear();
      const allYears = [];
      for (let year = 2020; year <= currentYear; year++) {
        allYears.push(year);
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/strava/activities/?years=${allYears.join(',')}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const activities = await response.json();
        const monthlyData = aggregateActivitiesData(activities);
        setActivityData(monthlyData);
      } else {
        console.error('Failed to fetch activities:', response.statusText);
      }
    } catch (error) {
      console.error('Error fetching activities:', error);
    }
  };

  // Aggregate activities data into monthly training hours format
  const aggregateActivitiesData = (activities) => {
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const monthlyTotals = {};

    activities.forEach(activity => {
      if (!activity.start_date_local && !activity.start_date) return;

      const activityDate = new Date(activity.start_date_local || activity.start_date);
      const year = activityDate.getFullYear();
      const month = activityDate.getMonth();
      const monthName = monthNames[month];

      // Convert elapsed time from seconds to hours
      const hours = (activity.elapsed_time || 0) / 3600;

      const key = `${year}-${month}`;
      if (!monthlyTotals[key]) {
        monthlyTotals[key] = {
          year,
          month: monthName,
          hours: 0
        };
      }
      monthlyTotals[key].hours += hours;
    });

    return Object.values(monthlyTotals);
  };

  // Load real data for authenticated non-demo users only
  useEffect(() => {
    if (isAuthenticated && user?.email !== process.env.NEXT_PUBLIC_DEMO_EMAIL) {
      fetchRealActivityData();
    }
  }, [isAuthenticated, user]);

  const resetToDefault = () => {
    setSelectedYears(['2023', '2024', '2025']);
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      {/* Navigation */}
      < Navigation />
      
      {/* Header */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="mb-6">
          <div className="flex items-center space-x-3 mb-2">
            <TrendingUp className="h-8 w-8" style={{ color: colors.primary }} />
            <h1 className="text-3xl font-bold" style={{ color: colors.foreground }}>
              Training Analytics
            </h1>
          </div>
          <div className="flex items-center space-x-2">
            <Calendar className="h-5 w-5" style={{ color: colors.mutedForeground }} />
            <span className="text-sm" style={{ color: colors.mutedForeground }}>
              Multi-year comparison and performance insights
            </span>
            {user && (
              <span className="text-xs px-2 py-1 rounded" style={{
                backgroundColor: (user.email === process.env.NEXT_PUBLIC_DEMO_EMAIL) ? colors.chart3 : colors.primary,
                color: 'white'
              }}>
                {(user.email === process.env.NEXT_PUBLIC_DEMO_EMAIL) ? 'Demo Data' : `${user.email}'s Data`}
              </span>
            )}
          </div>
        </div>

        <div className="space-y-6">
          {/* Controls */}
          <div className="rounded-xl shadow-sm" style={{ 
            backgroundColor: colors.card, 
            border: `1px solid ${colors.border}` 
          }}>
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>
                  Select Years to Compare (max 5)
                </h3>
                <button
                  onClick={resetToDefault}
                  className="flex items-center space-x-2 px-3 py-2 rounded-lg text-sm transition-colors hover:opacity-80"
                  style={{ 
                    backgroundColor: colors.muted,
                    color: colors.mutedForeground,
                    border: `1px solid ${colors.border}`
                  }}
                >
                  <RotateCcw className="h-4 w-4" />
                  <span>Reset</span>
                </button>
              </div>
              
              <div className="flex flex-wrap gap-3">
                {availableYears.map(year => (
                  <button
                    key={year}
                    onClick={() => handleYearToggle(year)}
                    disabled={!selectedYears.includes(year) && selectedYears.length >= 5}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      !selectedYears.includes(year) && selectedYears.length >= 5 
                        ? 'opacity-50 cursor-not-allowed' 
                        : 'hover:opacity-80'
                    }`}
                    style={{
                      backgroundColor: selectedYears.includes(year) 
                        ? getYearColor(selectedYears.indexOf(year))
                        : colors.muted,
                      color: selectedYears.includes(year) ? 'white' : colors.foreground,
                      border: `1px solid ${selectedYears.includes(year) 
                        ? getYearColor(selectedYears.indexOf(year))
                        : colors.border}`
                    }}
                  >
                    {year}
                  </button>
                ))}
              </div>

              {selectedYears.length >= 5 && (
                <p className="text-sm mt-3" style={{ color: colors.mutedForeground }}>
                  Maximum of 5 years can be selected for comparison
                </p>
              )}
            </div>
          </div>

          {/* Year Totals Summary */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {yearTotals.map((yearData, index) => (
              <div 
                key={yearData.year}
                className="p-4 rounded-lg"
                style={{ 
                  backgroundColor: colors.card,
                  border: `2px solid ${getYearColor(selectedYears.indexOf(yearData.year))}`
                }}
              >
                <div className="text-center">
                  <div className="text-2xl font-bold mb-1" style={{ 
                    color: getYearColor(selectedYears.indexOf(yearData.year)) 
                  }}>
                    {yearData.total.toFixed(1)}h
                  </div>
                  <div className="text-sm" style={{ color: colors.foreground }}>
                    {yearData.year} Total
                  </div>
                  {index === 0 && (
                    <div className="text-xs mt-1" style={{ color: colors.chart3 }}>
                      Best Year
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Main Chart */}
          <div className="rounded-xl shadow-sm" style={{ 
            backgroundColor: colors.card, 
            border: `1px solid ${colors.border}` 
          }}>
            <div className="p-6">
              <div className="mb-6">
                <h3 className="text-xl font-bold mb-2" style={{ color: colors.foreground }}>
                  Monthly Training Hours Comparison
                </h3>
                <p className="text-sm" style={{ color: colors.mutedForeground }}>
                  Compare your training volume across months for selected years
                </p>
              </div>
              
              <div className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    barCategoryGap="10%"
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
                    <XAxis 
                      dataKey="month" 
                      stroke={colors.mutedForeground}
                      fontSize={12}
                      fontWeight={500}
                    />
                    <YAxis 
                      stroke={colors.mutedForeground}
                      fontSize={12}
                      fontWeight={500}
                      label={{ 
                        value: 'Hours', 
                        angle: -90, 
                        position: 'insideLeft',
                        style: { textAnchor: 'middle', fill: colors.mutedForeground }
                      }}
                    />
                    <Tooltip 
                      contentStyle={{
                        backgroundColor: colors.card,
                        border: `1px solid ${colors.border}`,
                        borderRadius: '8px',
                        color: colors.foreground,
                        fontWeight: 500
                      }}
                      formatter={(value, name) => [`${value}h`, name]}
                      labelStyle={{ color: colors.foreground }}
                    />
                    <Legend 
                      wrapperStyle={{ 
                        paddingTop: '20px',
                        fontSize: '14px',
                        fontWeight: 500
                      }}
                    />
                    {selectedYears.map((year, index) => (
                      <Bar
                        key={year}
                        dataKey={year}
                        fill={getYearColor(index)}
                        name={year}
                        radius={[2, 2, 0, 0]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-4 text-center">
                <p className="text-xs" style={{ color: colors.mutedForeground }}>
                  Hover over bars to see exact values • Click year buttons above to modify comparison
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VisualizationsPage;
'use client';
import React, { useState } from 'react';

const SimpleActivitiesPage = () => {
  const [activities] = useState([
    {
      id: 1,
      dateTime: '2024-03-15 08:30',
      elapsedTime: 125,
      distance: 42.5,
      avgSpeed: 28.3,
      elevationGain: 450,
      avgPower: 245,
      normalisedPower: 268
    },
    {
      id: 2,
      dateTime: '2024-03-10 07:15',
      elapsedTime: 90,
      distance: 35.2,
      avgSpeed: 23.5,
      elevationGain: 320,
      avgPower: 220,
      normalisedPower: 235
    },
    {
      id: 3,
      dateTime: '2023-12-20 09:00',
      elapsedTime: 180,
      distance: 65.8,
      avgSpeed: 21.9,
      elevationGain: 890,
      avgPower: 210,
      normalisedPower: 225
    }
  ]);

  const formatElapsedTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  };

  const styles = {
    container: {
      minHeight: '100vh',
      backgroundColor: 'hsl(210, 10%, 15%)',
      color: 'hsl(210, 25%, 96.5%)',
      fontFamily: 'Arial, sans-serif'
    },
    header: {
      backgroundColor: 'hsl(210, 10%, 20%)',
      borderBottom: '1px solid hsl(210, 10%, 30%)',
      padding: '1rem 2rem',
      boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
    },
    nav: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      maxWidth: '1200px',
      margin: '0 auto'
    },
    logo: {
      fontSize: '1.5rem',
      fontWeight: 'bold',
      color: 'hsl(210, 25%, 96.5%)'
    },
    navMenu: {
      display: 'flex',
      gap: '1rem'
    },
    navButton: {
      padding: '0.5rem 1rem',
      borderRadius: '8px',
      border: 'none',
      cursor: 'pointer',
      fontSize: '0.9rem',
      fontWeight: '500',
      transition: 'all 0.2s'
    },
    navButtonActive: {
      backgroundColor: 'hsl(207, 44%, 49%)',
      color: 'white'
    },
    navButtonInactive: {
      backgroundColor: 'transparent',
      color: 'hsl(210, 15%, 65%)',
      border: '1px solid hsl(210, 10%, 30%)'
    },
    main: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '2rem'
    },
    title: {
      fontSize: '2rem',
      fontWeight: 'bold',
      marginBottom: '0.5rem',
      color: 'hsl(210, 25%, 96.5%)'
    },
    subtitle: {
      fontSize: '0.9rem',
      color: 'hsl(210, 15%, 65%)',
      marginBottom: '2rem'
    },
    card: {
      backgroundColor: 'hsl(210, 10%, 20%)',
      border: '1px solid hsl(210, 10%, 30%)',
      borderRadius: '12px',
      padding: '1.5rem',
      marginBottom: '1.5rem',
      boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
    },
    table: {
      width: '100%',
      borderCollapse: 'collapse',
      backgroundColor: 'hsl(210, 10%, 20%)',
      borderRadius: '8px',
      overflow: 'hidden'
    },
    tableHeader: {
      backgroundColor: 'hsl(210, 10%, 25%)',
      color: 'hsl(210, 25%, 96.5%)',
      fontWeight: '600',
      fontSize: '0.8rem',
      textTransform: 'uppercase',
      letterSpacing: '0.05em'
    },
    tableCell: {
      padding: '1rem',
      borderBottom: '1px solid hsl(210, 10%, 30%)',
      color: 'hsl(210, 15%, 65%)'
    },
    tableRow: {
      transition: 'background-color 0.2s'
    },
    tableRowHover: {
      backgroundColor: 'hsl(210, 10%, 25%)'
    },
    primaryColor: {
      color: 'hsl(207, 44%, 49%)'
    },
    accentColor: {
      color: 'hsl(16, 100%, 66%)'
    },
    successColor: {
      color: 'hsl(173, 58%, 39%)'
    }
  };

  return (
    <div style={styles.container}>

<div className="bg-red-500 text-white p-4 m-4 rounded-lg">
  <button className="bg-blue-500 px-4 py-2 rounded text-white">Test Tailwind</button>
</div>

      {/* Navigation */}
      <header style={styles.header}>
        <nav style={styles.nav}>
          <div style={styles.logo}>🚴 Veloclicks</div>
          <div style={styles.navMenu}>
            <button style={{...styles.navButton, ...styles.navButtonActive}}>
              Activities
            </button>
            <button style={{...styles.navButton, ...styles.navButtonInactive}}>
              Sync
            </button>
            <button style={{...styles.navButton, ...styles.navButtonInactive}}>
              Visualizations
            </button>
            <button style={{...styles.navButton, ...styles.navButtonInactive}}>
              Profile
            </button>
          </div>
        </nav>
      </header>

      {/* Main Content */}
      <main style={styles.main}>
        <h1 style={styles.title}>Training Activities</h1>
        <p style={styles.subtitle}>View and analyze your training activities</p>

        {/* Activities Table */}
        <div style={styles.card}>
          <h3 style={{...styles.title, fontSize: '1.2rem', marginBottom: '1rem'}}>
            Recent Activities
          </h3>
          
          <table style={styles.table}>
            <thead>
              <tr style={styles.tableHeader}>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>ID</th>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>Date/Time</th>
                <th style={{...styles.tableCell, ...styles.tableHeader, ...styles.successColor}}>
                  Elapsed Time
                </th>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>Distance (km)</th>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>Avg Speed (km/h)</th>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>Elevation (m)</th>
                <th style={{...styles.tableCell, ...styles.tableHeader}}>Avg Power (W)</th>
                <th style={{...styles.tableCell, ...styles.tableHeader, ...styles.accentColor}}>
                  Normalised Power (W)
                </th>
              </tr>
            </thead>
            <tbody>
              {activities.map((activity, index) => (
                <tr 
                  key={activity.id}
                  style={{
                    ...styles.tableRow,
                    backgroundColor: index % 2 === 0 ? 'hsl(210, 10%, 20%)' : 'hsl(210, 10%, 22%)'
                  }}
                  onMouseEnter={(e) => e.target.closest('tr').style.backgroundColor = 'hsl(210, 10%, 25%)'}
                  onMouseLeave={(e) => e.target.closest('tr').style.backgroundColor = 
                    index % 2 === 0 ? 'hsl(210, 10%, 20%)' : 'hsl(210, 10%, 22%)'
                  }
                >
                  <td style={{...styles.tableCell, ...styles.primaryColor, fontWeight: '600'}}>
                    {activity.id}
                  </td>
                  <td style={styles.tableCell}>
                    {new Date(activity.dateTime).toLocaleString()}
                  </td>
                  <td style={{...styles.tableCell, ...styles.successColor, fontWeight: '600'}}>
                    {formatElapsedTime(activity.elapsedTime)}
                  </td>
                  <td style={styles.tableCell}>
                    {activity.distance.toFixed(1)}
                  </td>
                  <td style={styles.tableCell}>
                    {activity.avgSpeed.toFixed(1)}
                  </td>
                  <td style={styles.tableCell}>
                    {activity.elevationGain}
                  </td>
                  <td style={styles.tableCell}>
                    {activity.avgPower}
                  </td>
                  <td style={{...styles.tableCell, ...styles.accentColor, fontWeight: '600'}}>
                    {activity.normalisedPower}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Stats Cards */}
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem'}}>
          <div style={styles.card}>
            <h4 style={{...styles.primaryColor, fontSize: '1.5rem', fontWeight: 'bold', margin: 0}}>
              {activities.length}
            </h4>
            <p style={{color: 'hsl(210, 15%, 65%)', margin: '0.5rem 0 0 0'}}>Total Activities</p>
          </div>
          
          <div style={styles.card}>
            <h4 style={{...styles.successColor, fontSize: '1.5rem', fontWeight: 'bold', margin: 0}}>
              {activities.reduce((sum, a) => sum + a.distance, 0).toFixed(1)} km
            </h4>
            <p style={{color: 'hsl(210, 15%, 65%)', margin: '0.5rem 0 0 0'}}>Total Distance</p>
          </div>
          
          <div style={styles.card}>
            <h4 style={{...styles.accentColor, fontSize: '1.5rem', fontWeight: 'bold', margin: 0}}>
              {Math.round(activities.reduce((sum, a) => sum + a.avgPower, 0) / activities.length)} W
            </h4>
            <p style={{color: 'hsl(210, 15%, 65%)', margin: '0.5rem 0 0 0'}}>Average Power</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default SimpleActivitiesPage;

'use client';
import React from 'react';

const WelcomePage = () => {
  // Dark theme colors matching your palette
  const colors = {
    foreground: 'hsl(210, 25%, 96.5%)',
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center px-4 sm:px-6 lg:px-8">
      {/* Mountain Road Background */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{
          backgroundImage: `url('/images/mountain-road.jpg')`,
          backgroundSize: 'cover'
        }}
      >
        {/* Dark overlay for better text contrast */}
        <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}></div>
      </div>

      {/* Welcome Content */}
      <div className="relative z-10 text-center">
        <h1 className="text-6xl md:text-7xl lg:text-8xl font-black tracking-tight" style={{
          color: colors.foreground,
          fontFamily: '"Inter", "Helvetica Neue", sans-serif',
          textShadow: '0 4px 8px rgba(0,0,0,0.7)'
        }}>
          Veloclicks
        </h1>
      </div>
    </div>
  );
};

export default WelcomePage;
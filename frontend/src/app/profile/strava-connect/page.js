'use client';
import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Navigation from '../../../components/Navigation';
import { Check, ArrowRight, Shield, Zap, BarChart3, AlertCircle, ExternalLink, Activity, RefreshCw, User } from 'lucide-react';

const StravaPartnerContent = () => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const searchParams = useSearchParams();

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

  // Check for errors from OAuth callback
  useEffect(() => {
    const errorParam = searchParams.get('error');
    if (errorParam) {
      setError(getErrorMessage(errorParam));
    }
  }, [searchParams]);

  const getErrorMessage = (errorCode) => {
    switch (errorCode) {
      case 'access_denied':
        return 'Authorization was cancelled. Please try again.';
      case 'missing_params':
        return 'Authorization failed due to missing parameters.';
      case 'token_exchange':
        return 'Failed to exchange authorization code. Please try again.';
      case 'user_not_found':
        return 'User account not found. Please ensure you are logged in.';
      case 'connection_failed':
        return 'Connection to Strava failed. Please try again.';
      default:
        return 'An error occurred during authorization. Please try again.';
    }
  };

  const handleStravaConnect = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      // Get current user ID from JWT token
      const token = localStorage.getItem('authToken');
      if (!token) {
        setError('Please log in first');
        setIsConnecting(false);
        return;
      }

      // Decode JWT to get user ID (simple decode, not validating signature)
      const payload = JSON.parse(atob(token.split('.')[1]));
      const userId = payload.user_id;

      // Strava OAuth configuration
      const clientId = '9899'; // Your Strava app client ID
      const redirectUri = encodeURIComponent(`${process.env.NEXT_PUBLIC_API_URL}/strava/strava_auth/`);
      const scope = 'read,activity:read_all';
      const state = userId; // Pass user ID as state for security

      // Build Strava OAuth URL
      const stravaAuthUrl = `https://www.strava.com/oauth/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&scope=${scope}&state=${state}`;

      // Debug logging
      console.log('=== STRAVA AUTH DEBUG ===');
      console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);
      console.log('Redirect URI (encoded):', redirectUri);
      console.log('Redirect URI (decoded):', decodeURIComponent(redirectUri));
      console.log('Full Strava URL:', stravaAuthUrl);
      console.log('========================');

      // Redirect to Strava OAuth
      window.location.href = stravaAuthUrl;

    } catch (error) {
      console.error('OAuth initiation error:', error);
      setError('Failed to start authorization. Please try again.');
      setIsConnecting(false);
    }
  };

  const benefits = [
    {
      icon: <Zap className="h-6 w-6" />,
      title: 'Automatic Sync',
      description: 'Your activities sync automatically from Strava to our platform'
    },
    {
      icon: <BarChart3 className="h-6 w-6" />,
      title: 'Advanced Analytics',
      description: 'Get deeper insights with our advanced performance analytics'
    },
    {
      icon: <Shield className="h-6 w-6" />,
      title: 'Secure Connection',
      description: 'Your data is encrypted and securely transferred via OAuth 2.0'
    }
  ];

  const permissions = [
    'Read your profile information',
    'Access your activity data (rides, runs, etc.)',
    'View activity details (power, heart rate, GPS)',
    'Read your segment efforts'
  ];

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      {/* Navigation */}
      < Navigation />
      

      {/* Background and Content */}
      <div className="relative min-h-screen flex items-center justify-center px-4 sm:px-6 lg:px-8 py-8">
        {/* Mountain Road Background */}
        <div 
          className="absolute inset-0 bg-cover bg-center bg-no-repeat"
          style={{
            backgroundImage: `url('/api/placeholder/1920/1080')`,
            backgroundSize: 'cover'
          }}
        >
          {/* Dark overlay for better text contrast */}
          <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}></div>
        </div>

        {/* Main Content */}
        <div className="relative z-10 max-w-2xl w-full">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex justify-center items-center mb-4">
              <div className="flex items-center space-x-3">
                {/* Your App Logo Placeholder */}
                <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: colors.primary }}>
                  <BarChart3 className="h-7 w-7 text-white" />
                </div>
                <ArrowRight className="h-6 w-6" style={{ color: colors.mutedForeground }} />
                {/* Strava Logo */}
                <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#fc4c02' }}>
                  <span className="text-white font-bold text-lg">S</span>
                </div>
              </div>
            </div>
            <h2 className="text-3xl font-bold mb-2" style={{ color: colors.foreground }}>
              Connect with Strava
            </h2>
            <p className="text-lg" style={{ color: colors.mutedForeground }}>
              Sync your activities and unlock advanced analytics
            </p>
          </div>

          {!isConnected ? (
            /* Connection Flow */
            <div className="space-y-6">
              {/* Benefits Card */}
              <div 
                className="p-6 rounded-xl shadow-2xl backdrop-blur-sm"
                style={{ 
                  backgroundColor: `${colors.card}CC`,
                  border: `1px solid ${colors.border}`
                }}
              >
                <h3 className="text-xl font-semibold mb-4" style={{ color: colors.foreground }}>
                  Why connect with Strava?
                </h3>
                <div className="space-y-4">
                  {benefits.map((benefit, index) => (
                    <div key={index} className="flex items-start space-x-3">
                      <div className="p-2 rounded-lg" style={{ backgroundColor: colors.primary }}>
                        {React.cloneElement(benefit.icon, { style: { color: 'white' } })}
                      </div>
                      <div>
                        <h4 className="font-medium" style={{ color: colors.foreground }}>
                          {benefit.title}
                        </h4>
                        <p className="text-sm" style={{ color: colors.mutedForeground }}>
                          {benefit.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Permissions Card */}
              <div 
                className="p-6 rounded-xl shadow-2xl backdrop-blur-sm"
                style={{ 
                  backgroundColor: `${colors.card}CC`,
                  border: `1px solid ${colors.border}`
                }}
              >
                <h3 className="text-lg font-semibold mb-4" style={{ color: colors.foreground }}>
                  Permissions Required
                </h3>
                <div className="space-y-2">
                  {permissions.map((permission, index) => (
                    <div key={index} className="flex items-center space-x-3">
                      <Check className="h-4 w-4" style={{ color: colors.chart3 }} />
                      <span className="text-sm" style={{ color: colors.mutedForeground }}>
                        {permission}
                      </span>
                    </div>
                  ))}
                </div>
                
                <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                  <div className="flex items-start space-x-2">
                    <Shield className="h-5 w-5 mt-0.5" style={{ color: colors.chart3 }} />
                    <div>
                      <p className="text-sm font-medium" style={{ color: colors.foreground }}>
                        Your data is secure
                      </p>
                      <p className="text-xs" style={{ color: colors.mutedForeground }}>
                        We only access the data you explicitly grant permission for. You can revoke access at any time.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error Display */}
              {error && (
                <div
                  className="p-4 rounded-xl shadow-2xl backdrop-blur-sm"
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)'
                  }}
                >
                  <div className="flex items-center space-x-3">
                    <AlertCircle className="h-5 w-5 text-red-400" />
                    <span className="text-sm text-red-400">{error}</span>
                  </div>
                </div>
              )}

              {/* Connect Button */}
              <button
                onClick={handleStravaConnect}
                disabled={isConnecting}
                className={`w-full flex items-center justify-center py-4 px-6 rounded-xl shadow-lg text-white font-semibold text-lg transition-all duration-200 ${
                  isConnecting ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90 transform hover:scale-105'
                }`}
                style={{ backgroundColor: '#fc4c02' }}
              >
                {isConnecting ? (
                  <div className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Connecting to Strava...
                  </div>
                ) : (
                  <div className="flex items-center">
                    <span>Connect with Strava</span>
                    <ExternalLink className="ml-2 h-5 w-5" />
                  </div>
                )}
              </button>

              {/* Skip Option */}
              <div className="text-center">
                <button
                  type="button"
                  className="text-sm hover:opacity-80 transition-colors"
                  style={{ color: colors.mutedForeground }}
                  onClick={() => alert('Skip for now - navigate to main app')}
                >
                  Skip for now, I'll connect later
                </button>
              </div>
            </div>
          ) : (
            /* Success State */
            <div 
              className="p-8 rounded-xl shadow-2xl backdrop-blur-sm text-center"
              style={{ 
                backgroundColor: `${colors.card}CC`,
                border: `1px solid ${colors.chart3}`
              }}
            >
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-4" style={{ backgroundColor: colors.chart3 }}>
                  <Check className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-2" style={{ color: colors.foreground }}>
                  Successfully Connected!
                </h3>
                <p className="text-lg" style={{ color: colors.mutedForeground }}>
                  Your Strava account is now linked
                </p>
              </div>

              <div className="space-y-4 mb-6">
                <div className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                  <span className="text-sm" style={{ color: colors.foreground }}>Connected Account</span>
                  <span className="text-sm font-medium" style={{ color: colors.chart3 }}>John Cyclist</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                  <span className="text-sm" style={{ color: colors.foreground }}>Last Sync</span>
                  <span className="text-sm font-medium" style={{ color: colors.chart3 }}>Just now</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                  <span className="text-sm" style={{ color: colors.foreground }}>Activities Found</span>
                  <span className="text-sm font-medium" style={{ color: colors.accent }}>127 activities</span>
                </div>
              </div>

              <button
                type="button"
                className="w-full py-3 px-4 rounded-lg font-medium transition-colors hover:opacity-90"
                style={{ backgroundColor: colors.primary, color: 'white' }}
                onClick={() => alert('Navigate to main dashboard')}
              >
                Continue to Dashboard
              </button>

              <div className="mt-4">
                <button
                  type="button"
                  className="text-sm hover:opacity-80 transition-colors"
                  style={{ color: colors.mutedForeground }}
                  onClick={() => setIsConnected(false)}
                >
                  Disconnect from Strava
                </button>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="text-center text-xs mt-6" style={{ color: colors.mutedForeground }}>
            <p>
              By connecting, you agree to Strava's{' '}
              <button className="underline hover:opacity-80" style={{ color: colors.primary }}>
                Terms of Service
              </button>
              {' '}and our{' '}
              <button className="underline hover:opacity-80" style={{ color: colors.primary }}>
                Data Usage Policy
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

const StravaPartnerPage = () => {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'hsl(210, 10%, 15%)' }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p style={{ color: 'hsl(210, 25%, 96.5%)' }}>Loading Strava connection...</p>
        </div>
      </div>
    }>
      <StravaPartnerContent />
    </Suspense>
  );
};

export default StravaPartnerPage;

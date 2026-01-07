'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Navigation from '../../components/Navigation';
import { User, Calendar, Zap, Heart, Save, Edit3, RefreshCw, ExternalLink, Settings, Shield } from 'lucide-react';

const ProfilePage = () => {
  const router = useRouter();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profileData, setProfileData] = useState({
    username: '',
    email: '',
    firstname: '',
    lastname: '',
    sex: '',
    date_of_birth: '',
    ftp: null,
    max_heart_rate: null,
    resting_heart_rate: null,
    zones: []
  });

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

  // Fetch profile data on component mount
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const token = localStorage.getItem('authToken');
        if (!token) {
          setError('Not authenticated');
          setIsLoading(false);
          return;
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/profile`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          console.log('Profile data received:', data);
          console.log('Membership type:', data.membership_type);
          setProfileData(data);
        } else {
          setError('Failed to load profile');
        }
      } catch (error) {
        console.error('Error fetching profile:', error);
        setError('Network error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfile();
  }, []);

  // Navigation menu component
  const NavigationMenu = () => (
    <div className="shadow-lg" style={{ backgroundColor: colors.card, borderBottom: `1px solid ${colors.border}` }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: colors.primary }}>
                <Zap className="h-5 w-5 text-white" />
              </div>
              <span className="text-xl font-bold" style={{ color: colors.foreground }}>Veloclicks</span>
            </div>
            
            <nav className="flex space-x-6">
              <button 
                className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                style={{ color: colors.mutedForeground }}
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
                className="px-3 py-2 rounded-lg text-sm font-medium"
                style={{ 
                  backgroundColor: colors.primary, 
                  color: 'white'
                }}
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
  );

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfileData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);

    try {
      const token = localStorage.getItem('authToken');
      if (!token) {
        setError('Not authenticated');
        setIsSaving(false);
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/profile`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profileData),
      });

      if (response.ok) {
        setIsEditing(false);
        alert('Profile updated successfully!');
      } else {
        const data = await response.json();
        setError(data.message || 'Failed to update profile');
      }
    } catch (error) {
      console.error('Error saving profile:', error);
      setError('Network error');
    } finally {
      setIsSaving(false);
    }
  };

  const calculateAge = (dateOfBirth) => {
    const today = new Date();
    const birthDate = new Date(dateOfBirth);
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    
    return age;
  };

  // Check if user has Strava tokens (indicating connection)
  const isStravaConnected = profileData.strava_access_token && profileData.strava_refresh_token;

  const partners = [
    {
      name: 'Strava',
      description: 'Sync your activities automatically',
      icon: (
        <img
          src="https://upload.wikimedia.org/wikipedia/commons/c/cb/Strava_Logo.svg"
          alt="Strava"
          className="w-6 h-6"
        />
      ),
      status: isStravaConnected ? 'connected' : 'available',
      lastSync: null, // Will be populated dynamically if connected
      color: '#fc4c02'
    },
    // Commenting out until implemented
    // {
    //   name: 'Garmin Connect',
    //   description: 'Import activities and device data',
    //   icon: '⌚',
    //   status: 'available',
    //   color: colors.primary
    // },
    // {
    //   name: 'TrainingPeaks',
    //   description: 'Advanced training analytics',
    //   icon: '📊',
    //   status: 'available',
    //   color: colors.chart3
    // }
  ];

  if (isLoading) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center" style={{ color: colors.foreground }}>
            Loading profile...
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
        <Navigation />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center" style={{ color: 'red' }}>
            Error: {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: colors.background }}>
      {/* Navigation */}
      <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Profile Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold" style={{ color: colors.foreground }}>
                Profile Settings
              </h1>
              <p className="text-sm mt-1" style={{ color: colors.mutedForeground }}>
                Manage your account and training data preferences
              </p>
            </div>
            
            <button
              onClick={() => isEditing ? handleSave() : setIsEditing(true)}
              disabled={isSaving}
              className="flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors hover:opacity-90"
              style={{ 
                backgroundColor: isEditing ? colors.chart3 : colors.primary, 
                color: 'white' 
              }}
            >
              {isSaving ? (
                <>
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Saving...</span>
                </>
              ) : isEditing ? (
                <>
                  <Save className="h-4 w-4" />
                  <span>Save Changes</span>
                </>
              ) : (
                <>
                  <Edit3 className="h-4 w-4" />
                  <span>Edit Profile</span>
                </>
              )}
            </button>
          </div>
        </div>

        <div className="space-y-6">
          {/* Basic Information */}
          <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
            <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>
              Personal Information
            </h3>

            <div className="space-y-1">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
                <div className="flex items-center space-x-3">
                  <label className="text-sm font-medium min-w-[100px]" style={{ color: colors.foreground }}>
                    First Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="firstname"
                      value={profileData.firstname}
                      onChange={handleInputChange}
                      className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    />
                  ) : (
                    <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                      {profileData.firstname || 'Not set'}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <label className="text-sm font-medium min-w-[100px]" style={{ color: colors.foreground }}>
                    Last Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="lastname"
                      value={profileData.lastname}
                      onChange={handleInputChange}
                      className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    />
                  ) : (
                    <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                      {profileData.lastname || 'Not set'}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <label className="text-sm font-medium min-w-[100px]" style={{ color: colors.foreground }}>
                    Sex
                  </label>
                  {isEditing ? (
                    <select
                      name="sex"
                      value={profileData.sex}
                      onChange={handleInputChange}
                      className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                      <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                  ) : (
                    <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                      {profileData.sex || 'Not set'}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <label className="text-sm font-medium min-w-[100px]" style={{ color: colors.foreground }}>
                    Date of Birth
                  </label>
                  {isEditing ? (
                    <input
                      type="date"
                      name="date_of_birth"
                      value={profileData.date_of_birth}
                      onChange={handleInputChange}
                      className="px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    />
                  ) : (
                    <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                      {profileData.date_of_birth ? (
                        <>
                          {new Date(profileData.date_of_birth).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          })} (Age: {calculateAge(profileData.date_of_birth)})
                        </>
                      ) : (
                        'Not set'
                      )}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Membership */}
          <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
            <div className="flex items-center space-x-2 mb-3">
              <Shield className="h-5 w-5" style={{ color: colors.accent }} />
              <h3 className="text-lg font-semibold" style={{ color: colors.foreground }}>
                Membership
              </h3>
            </div>

            <div className="flex items-center space-x-3">
              <label className="text-sm font-medium min-w-[100px]" style={{ color: colors.foreground }}>
                Current Plan
              </label>
              <span
                className="px-3 py-1 rounded-full text-sm font-medium"
                style={{
                  backgroundColor: profileData.membership_type === 'PREMIUM_TIER' ? colors.accent : colors.muted,
                  color: profileData.membership_type === 'PREMIUM_TIER' ? 'white' : colors.mutedForeground
                }}
              >
                {profileData.membership_type === 'PREMIUM_TIER' ? 'Premium' : 'Free'}
              </span>
            </div>

            {profileData.membership_type !== 'PREMIUM_TIER' && (
              <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: colors.muted, border: `1px solid ${colors.border}` }}>
                <p className="text-xs" style={{ color: colors.mutedForeground }}>
                  Upgrade to Premium to unlock AI-powered training insights, advanced analytics, and more features.
                </p>
              </div>
            )}
          </div>

          {/* Training Metrics */}
          <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
            <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>
              Training Metrics
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
              <div className="flex items-center space-x-3">
                <label className="text-sm font-medium min-w-[120px]" style={{ color: colors.foreground }}>
                  FTP
                </label>
                {isEditing ? (
                  <input
                    type="number"
                    name="ftp"
                    value={profileData.ftp || ''}
                    onChange={handleInputChange}
                    min="1"
                    className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                    style={{
                      backgroundColor: colors.muted,
                      border: `1px solid ${colors.border}`,
                      color: colors.foreground
                    }}
                  />
                ) : (
                  <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                    {profileData.ftp ? `${profileData.ftp} W` : 'Not set'}
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3">
                <label className="text-sm font-medium min-w-[120px]" style={{ color: colors.foreground }}>
                  Max Heart Rate
                </label>
                {isEditing ? (
                  <input
                    type="number"
                    name="max_heart_rate"
                    value={profileData.max_heart_rate || ''}
                    onChange={handleInputChange}
                    min="1"
                    className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                    style={{
                      backgroundColor: colors.muted,
                      border: `1px solid ${colors.border}`,
                      color: colors.foreground
                    }}
                  />
                ) : (
                  <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                    {profileData.max_heart_rate ? `${profileData.max_heart_rate} bpm` : 'Not set'}
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3">
                <label className="text-sm font-medium min-w-[120px]" style={{ color: colors.foreground }}>
                  Resting Heart Rate
                </label>
                {isEditing ? (
                  <input
                    type="number"
                    name="resting_heart_rate"
                    value={profileData.resting_heart_rate || ''}
                    onChange={handleInputChange}
                    min="1"
                    className="flex-1 px-2 py-1 text-sm rounded focus:outline-none focus:ring-1"
                    style={{
                      backgroundColor: colors.muted,
                      border: `1px solid ${colors.border}`,
                      color: colors.foreground
                    }}
                  />
                ) : (
                  <span className="text-[11px]" style={{ color: colors.mutedForeground }}>
                    {profileData.resting_heart_rate ? `${profileData.resting_heart_rate} bpm` : 'Not set'}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Training Zones */}
          <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
            <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>
              Training Zones
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Power Zones */}
              <div>
                <h4 className="text-sm font-semibold mb-2" style={{ color: colors.accent }}>
                  Power Zones
                </h4>
                {profileData.ftp && profileData.zones && profileData.zones.filter(z => z.type === 'power').length > 0 ? (
                  <div>
                    {profileData.zones
                      .filter(z => z.type === 'power')
                      .map((zone, index, array) => (
                        <div
                          key={index}
                          className="flex items-center justify-between px-2 py-1"
                          style={{ backgroundColor: index % 2 === 0 ? colors.muted : colors.card }}
                        >
                          <span className="text-[11px]" style={{ color: colors.mutedForeground }}>{zone.display_name}</span>
                          <span className="text-sm font-medium" style={{ color: colors.foreground }}>
                            {index === array.length - 1 ? `${zone.min_value}+ W` : `${zone.min_value}-${zone.max_value} W`}
                          </span>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div className="text-sm" style={{ color: colors.mutedForeground }}>
                    Unset
                  </div>
                )}
              </div>

              {/* Heart Rate Zones */}
              <div>
                <h4 className="text-sm font-semibold mb-2" style={{ color: colors.primary }}>
                  Heart Rate Zones
                </h4>
                {profileData.max_heart_rate && profileData.zones && profileData.zones.filter(z => z.type === 'heart_rate').length > 0 ? (
                  <div>
                    {profileData.zones
                      .filter(z => z.type === 'heart_rate')
                      .map((zone, index, array) => (
                        <div
                          key={index}
                          className="flex items-center justify-between px-2 py-1"
                          style={{ backgroundColor: index % 2 === 0 ? colors.muted : colors.card }}
                        >
                          <span className="text-[11px]" style={{ color: colors.mutedForeground }}>{zone.display_name}</span>
                          <span className="text-sm font-medium" style={{ color: colors.foreground }}>
                            {index === array.length - 1 ? `${zone.min_value}+ bpm` : `${zone.min_value}-${zone.max_value} bpm`}
                          </span>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div className="text-sm" style={{ color: colors.mutedForeground }}>
                    Unset
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Partner Registrations */}
          <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
            <h3 className="text-lg font-semibold mb-3" style={{ color: colors.foreground }}>
              Partner Registrations
            </h3>
            <p className="text-xs mb-3" style={{ color: colors.mutedForeground }}>
              Connect your accounts to automatically sync activities and data
            </p>

            <div className="space-y-2">
              {partners.map((partner, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 rounded-lg"
                  style={{ backgroundColor: colors.muted, border: `1px solid ${colors.border}` }}
                >
                  <div className="flex items-center space-x-3">
                    <div className="text-xl">
                      {typeof partner.icon === 'string' ? partner.icon : partner.icon}
                    </div>
                    <div>
                      <h4 className="font-medium text-sm" style={{ color: colors.foreground }}>
                        {partner.name}
                      </h4>
                      <p className="text-xs" style={{ color: colors.mutedForeground }}>
                        {partner.description}
                      </p>
                      {partner.status === 'connected' && (
                        <p className="text-xs mt-0.5" style={{ color: colors.chart3 }}>
                          Connected and syncing
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {partner.status === 'connected' ? (
                      <>
                        <span className="px-2 py-1 rounded-full text-xs font-medium" style={{
                          backgroundColor: colors.chart3,
                          color: 'white'
                        }}>
                          Connected
                        </span>
                        <button
                          className="text-xs hover:opacity-80 transition-colors"
                          style={{ color: colors.mutedForeground }}
                          onClick={() => alert('Disconnect from ' + partner.name)}
                        >
                          Disconnect
                        </button>
                      </>
                    ) : (
                      <button
                        className="flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
                        style={{ backgroundColor: partner.color, color: 'white' }}
                        onClick={() => {
                          if (partner.name === 'Strava') {
                            router.push('/profile/strava-connect');
                          } else {
                            alert('Navigate to ' + partner.name + ' registration');
                          }
                        }}
                      >
                        <span>Connect</span>
                        <ExternalLink className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
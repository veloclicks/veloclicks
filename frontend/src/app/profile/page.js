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
    ftp: '',
    max_heart_rate: ''
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

  const StatCard = ({ icon, label, value, unit, color = colors.foreground, isEditable = false, name, type = "text" }) => (
    <div className="p-4 rounded-lg" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
      <div className="flex items-center space-x-3">
        <div className="p-2 rounded-lg" style={{ backgroundColor: colors.muted }}>
          {React.cloneElement(icon, { className: 'h-5 w-5', style: { color } })}
        </div>
        <div className="flex-1">
          <div className="text-sm mb-1" style={{ color: colors.mutedForeground }}>{label}</div>
          {isEditable && isEditing ? (
            <div className="flex items-center space-x-2">
              <input
                type={type}
                name={name}
                value={profileData[name]}
                onChange={handleInputChange}
                className="bg-transparent border-b border-current text-lg font-bold focus:outline-none"
                style={{ color, borderColor: color }}
              />
              {unit && <span className="text-sm" style={{ color: colors.mutedForeground }}>{unit}</span>}
            </div>
          ) : (
            <div className="text-lg font-bold" style={{ color }}>
              {value}
              {unit && <span className="text-sm ml-1" style={{ color: colors.mutedForeground }}>{unit}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );

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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Personal Information */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Information */}
            <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: colors.foreground }}>
                Personal Information
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                    First Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="firstname"
                      value={profileData.firstname}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground,
                        focusRingColor: colors.primary
                      }}
                    />
                  ) : (
                    <div className="px-3 py-2" style={{ color: colors.foreground }}>
                      {profileData.firstname}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                    Last Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="lastname"
                      value={profileData.lastname}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    />
                  ) : (
                    <div className="px-3 py-2" style={{ color: colors.foreground }}>
                      {profileData.lastname}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                    Email
                  </label>
                  <div className="px-3 py-2" style={{ color: colors.mutedForeground }}>
                    {profileData.email} (cannot be changed)
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                    Sex
                  </label>
                  {isEditing ? (
                    <select
                      name="sex"
                      value={profileData.sex}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2"
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
                    <div className="px-3 py-2" style={{ color: colors.foreground }}>
                      {profileData.sex}
                    </div>
                  )}
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                    Date of Birth
                  </label>
                  {isEditing ? (
                    <input
                      type="date"
                      name="date_of_birth"
                      value={profileData.date_of_birth}
                      onChange={handleInputChange}
                      className="w-full px-3 py-2 rounded-lg focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: colors.muted,
                        border: `1px solid ${colors.border}`,
                        color: colors.foreground
                      }}
                    />
                  ) : (
                    <div className="px-3 py-2" style={{ color: colors.foreground }}>
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
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Partner Registrations */}
            <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: colors.foreground }}>
                Partner Registrations
              </h3>
              <p className="text-sm mb-4" style={{ color: colors.mutedForeground }}>
                Connect your accounts to automatically sync activities and data
              </p>
              
              <div className="space-y-3">
                {partners.map((partner, index) => (
                  <div 
                    key={index}
                    className="flex items-center justify-between p-4 rounded-lg"
                    style={{ backgroundColor: colors.muted, border: `1px solid ${colors.border}` }}
                  >
                    <div className="flex items-center space-x-4">
                      <div className="text-2xl">
                        {typeof partner.icon === 'string' ? partner.icon : partner.icon}
                      </div>
                      <div>
                        <h4 className="font-medium" style={{ color: colors.foreground }}>
                          {partner.name}
                        </h4>
                        <p className="text-sm" style={{ color: colors.mutedForeground }}>
                          {partner.description}
                        </p>
                        {partner.status === 'connected' && (
                          <p className="text-xs mt-1" style={{ color: colors.chart3 }}>
                            Connected and syncing
                          </p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      {partner.status === 'connected' ? (
                        <>
                          <span className="px-2 py-1 rounded-full text-xs font-medium" style={{ 
                            backgroundColor: colors.chart3, 
                            color: 'white' 
                          }}>
                            Connected
                          </span>
                          <button
                            className="text-sm hover:opacity-80 transition-colors"
                            style={{ color: colors.mutedForeground }}
                            onClick={() => alert('Disconnect from ' + partner.name)}
                          >
                            Disconnect
                          </button>
                        </>
                      ) : (
                        <button
                          className="flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
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

          {/* Right Column - Training Metrics */}
          <div className="space-y-6">
            <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: colors.foreground }}>
                Training Metrics
              </h3>
              
              <div className="space-y-4">
                <StatCard
                  icon={<Zap />}
                  label="Functional Threshold Power (FTP)"
                  value={profileData.ftp || 'Not set'}
                  unit={profileData.ftp ? "W" : ""}
                  color={colors.accent}
                  isEditable={true}
                  name="ftp"
                  type="number"
                />

                <StatCard
                  icon={<Heart />}
                  label="Max Heart Rate"
                  value={profileData.max_heart_rate || 'Not set'}
                  unit={profileData.max_heart_rate ? "bpm" : ""}
                  color={colors.primary}
                  isEditable={true}
                  name="max_heart_rate"
                  type="number"
                />
              </div>
              
              <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: colors.muted }}>
                <div className="flex items-start space-x-2">
                  <Settings className="h-4 w-4 mt-0.5" style={{ color: colors.chart3 }} />
                  <div>
                    <p className="text-sm font-medium" style={{ color: colors.foreground }}>
                      Why these matter
                    </p>
                    <p className="text-xs" style={{ color: colors.mutedForeground }}>
                      FTP and Max HR are used to calculate training zones and analyze your performance data accurately.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Account Security */}
            <div className="rounded-lg p-6" style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}` }}>
              <h3 className="text-lg font-semibold mb-4" style={{ color: colors.foreground }}>
                Account Security
              </h3>
              
              <div className="space-y-3">
                <button
                  className="w-full flex items-center justify-between p-3 rounded-lg transition-colors hover:opacity-80"
                  style={{ backgroundColor: colors.muted }}
                  onClick={() => alert('Change password functionality')}
                >
                  <div className="flex items-center space-x-3">
                    <Shield className="h-4 w-4" style={{ color: colors.primary }} />
                    <span style={{ color: colors.foreground }}>Change Password</span>
                  </div>
                  <span style={{ color: colors.mutedForeground }}>›</span>
                </button>
                
                <button
                  className="w-full flex items-center justify-between p-3 rounded-lg transition-colors hover:opacity-80"
                  style={{ backgroundColor: colors.muted }}
                  onClick={() => alert('Two-factor authentication setup')}
                >
                  <div className="flex items-center space-x-3">
                    <Shield className="h-4 w-4" style={{ color: colors.chart3 }} />
                    <span style={{ color: colors.foreground }}>Two-Factor Authentication</span>
                  </div>
                  <span style={{ color: colors.mutedForeground }}>›</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
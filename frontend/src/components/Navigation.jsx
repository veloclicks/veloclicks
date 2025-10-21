'use client';
import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Activity, RefreshCw, User, LogOut } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const Navigation = () => {
  const router = useRouter();
  const pathname = usePathname();
  const [isSyncing, setIsSyncing] = useState(false);
  const { isAuthenticated, user, logout, isDemoMode } = useAuth();

  // Check for auth token or demo mode on mount - redirect to login if neither found
  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const demoMode = localStorage.getItem('demoMode') === 'true';

    if (!token && !demoMode) {
      router.push('/login');
      return;
    }
  }, [router]);

  const colors = {
    background: 'hsl(210, 10%, 15%)',
    card: 'hsl(210, 10%, 20%)',
    foreground: 'hsl(210, 25%, 96.5%)',
    primary: 'hsl(207, 44%, 49%)',
    muted: 'hsl(210, 10%, 25%)',
    mutedForeground: 'hsl(210, 15%, 65%)',
    border: 'hsl(210, 10%, 30%)',
  };

  const isActive = (path) => pathname === path;

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
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
                className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                style={isActive('/activities') ? { 
                  backgroundColor: colors.primary, 
                  color: 'white'
                } : { color: colors.mutedForeground }}
                onClick={() => router.push('/activities')}
              >
                Activities
              </button>
              
              {!isDemoMode && (
                <button
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80 flex items-center space-x-2"
                  style={{ color: colors.mutedForeground }}
                  onClick={async () => {
                    if (isSyncing) return; // Prevent multiple syncs

                    setIsSyncing(true);
                    try {
                      const token = localStorage.getItem('authToken');
                      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/strava/synch/`, {
                        headers: {
                          'Authorization': `Bearer ${token}`,
                          'Content-Type': 'application/json',
                        },
                      });
                      if (response.ok) {
                        const data = await response.json();
                        if (data.success && data.new_activities > 0) {
                          // New activities were added, redirect with refresh flag
                          router.push('/activities?refresh=true');
                        } else {
                          // No new activities, just go to activities page
                          router.push('/activities');
                        }

                        // Show user feedback about sync result
                        if (data.success) {
                          alert(data.message);
                        }
                      } else {
                        alert('Sync failed. Please try again.');
                      }
                    } catch (error) {
                      console.error('Sync error:', error);
                      alert('Sync failed. Please check your connection.');
                    } finally {
                      setIsSyncing(false);
                    }
                  }}
                >
                  <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                  <span>Sync</span>
                </button>
              )}
              
              <button 
                className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                style={isActive('/visualizations') ? { 
                  backgroundColor: colors.primary, 
                  color: 'white'
                } : { color: colors.mutedForeground }}
                onClick={() => router.push('/visualizations')}
              >
                Visualizations
              </button>
              
            </nav>
          </div>
          
          <div className="flex items-center space-x-3">
            {true && (
              <>
                <div className="flex items-center space-x-2">
                  {!isDemoMode && (
                    <button
                      className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:opacity-80"
                      style={{
                        backgroundColor: isActive('/profile') ? colors.primary : colors.muted
                      }}
                      onClick={() => router.push('/profile')}
                      title="Profile"
                    >
                      <User className="h-5 w-5" style={{
                        color: isActive('/profile') ? 'white' : colors.foreground
                      }} />
                    </button>
                  )}
                  {user && (
                    <span className="text-sm font-medium" style={{ color: colors.foreground }}>
                      {isDemoMode ? 'Demo User' : user.email}
                    </span>
                  )}
                </div>
                <button
                  className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:opacity-80"
                  style={{ backgroundColor: colors.muted }}
                  onClick={handleLogout}
                  title="Logout"
                >
                  <LogOut className="h-5 w-5" style={{ color: colors.foreground }} />
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Navigation;

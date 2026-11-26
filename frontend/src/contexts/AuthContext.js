'use client';
import React, { createContext, useContext, useState, useEffect } from 'react';

// Simple JWT decoder (just for reading payload, not for security validation)
const decodeJWT = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (error) {
    return null;
  }
};

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [authToken, setAuthToken] = useState(null);
  const [loginSerial, setLoginSerial] = useState(0);
  const [isDemoMode, setIsDemoMode] = useState(false);

  // Initialize auth state from token on client-side mount
  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const demoMode = localStorage.getItem('demoMode') === 'true';

    if (demoMode) {
      setIsDemoMode(true);
      setIsAuthenticated(true);
      setUser({
        user_id: 'demo',
        email: 'demo@veloclicks.com',
        username: 'demo'
      });
    } else if (token) {
      setAuthToken(token);
      setIsAuthenticated(true);
      const decoded = decodeJWT(token);

      if (decoded) {
        setUser({
          user_id: decoded.user_id,
          email: decoded.email
        });
      }
    } else {
      setIsAuthenticated(false);
      setUser(null);
      setIsDemoMode(false);
    }
  }, []);

  // Check authentication status and fetch user profile
  const checkAuth = async () => {
    try {
      // Skip API validation for demo mode
      if (isDemoMode || localStorage.getItem('demoMode') === 'true') {
        return;
      }

      const token = localStorage.getItem('authToken');
      if (!token) {
        setIsAuthenticated(false);
        setUser(null);
        return;
      }

      // Fetch user profile
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/profile`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (localStorage.getItem('authToken') !== token) return;
      if (response.ok) {
        const userData = await response.json();
        if (localStorage.getItem('authToken') !== token) return;
        setIsAuthenticated(true);
        setUser({ user_id: decodeJWT(token)?.user_id, ...userData });
      } else if (response.status === 401 || response.status === 404) {
        localStorage.removeItem('authToken');
        setAuthToken(null);
        setIsAuthenticated(false);
        setUser(null);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    }
  };

  // Login function
  const login = (token, userData = null) => {
    localStorage.removeItem('demoMode');
    localStorage.setItem('authToken', token);
    setIsDemoMode(false);
    setAuthToken(token);
    setLoginSerial(serial => serial + 1);
    setIsAuthenticated(true);

    // Decode token immediately to get basic user info
    const decoded = decodeJWT(token);
    if (decoded) {
      setUser({
        user_id: decoded.user_id,
        email: decoded.email
      });
    }

    if (userData) {
      // Merge with any additional user data provided
      setUser(prev => ({ ...prev, ...userData }));
    } else {
      // Still trigger profile fetch for additional details
      checkAuth();
    }
  };

  // Demo login function
  const loginDemo = () => {
    localStorage.setItem('demoMode', 'true');
    localStorage.removeItem('authToken'); // Clear any existing token
    setAuthToken(null);
    setIsDemoMode(true);
    setIsAuthenticated(true);
    setUser({
      user_id: 'demo',
      email: 'demo@veloclicks.com',
      username: 'demo'
    });
  };

  // Logout function
  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('demoMode');
    setAuthToken(null);
    setIsAuthenticated(false);
    setUser(null);
    setIsDemoMode(false);
  };

  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    function onStorage(event) {
      if (event.key !== 'authToken') return;
      const token = localStorage.getItem('authToken');
      const decoded = token && decodeJWT(token);
      setAuthToken(token);
      setIsAuthenticated(Boolean(token));
      setIsDemoMode(false);
      setUser(decoded ? { user_id: decoded.user_id, email: decoded.email } : null);
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const value = {
    isAuthenticated,
    authToken,
    loginSerial,
    user,
    isDemoMode,
    login,
    loginDemo,
    logout,
    checkAuth
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, Activity, Lock, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const LoginPage = () => {
    const router = useRouter();
    const { login, loginDemo } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false
  });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);

  // Dark theme colors matching your palette
  const colors = {
    background: 'hsl(210, 10%, 15%)',
    card: 'hsl(210, 10%, 20%)',
    foreground: 'hsl(210, 25%, 96.5%)',
    primary: 'hsl(207, 44%, 49%)',
    accent: 'hsl(16, 100%, 66%)',
    muted: 'hsl(210, 10%, 25%)',
    mutedForeground: 'hsl(210, 15%, 65%)',
    border: 'hsl(210, 10%, 30%)',
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.email) {
      newErrors.email = 'Username/Email is required';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.email, // Backend expects 'username' but frontend uses 'email'
          password: formData.password,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Use AuthContext login function to store token and set user state
        login(data.token);

        // Redirect to activities page
        router.push('/activities');
      } else {
        // Show error message
        setErrors({ general: data.message || 'Login failed' });
      }
    } catch (error) {
      console.error('Login error:', error);
      setErrors({ general: 'Network error. Please try again.' });
    } finally {
      setIsLoading(false);
    }
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

      {/* Login Form */}
      <div className="relative z-10 max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-black tracking-tight mb-2" style={{
            color: colors.foreground,
            fontFamily: '"Inter", "Helvetica Neue", sans-serif',
            textShadow: '0 2px 4px rgba(0,0,0,0.5)'
          }}>
            Veloclicks
          </h1>
        </div>

        {/* Form Card */}
        <div 
          className="p-8 rounded-xl shadow-2xl backdrop-blur-sm"
          style={{ 
            backgroundColor: `${colors.card}CC`, // Semi-transparent
            border: `1px solid ${colors.border}`
          }}
        >
          <div className="space-y-6">
            {/* Email Field */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                Username or Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  className={`block w-full pl-10 pr-3 py-3 rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                    errors.email ? 'ring-2 ring-red-500' : ''
                  }`}
                  style={{
                    backgroundColor: colors.muted,
                    border: `1px solid ${errors.email ? '#ef4444' : colors.border}`,
                    color: colors.foreground,
                    focusRingColor: colors.primary
                  }}
                  placeholder="Enter your username or email"
                />
              </div>
              {errors.email && (
                <div className="mt-1 flex items-center text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.email}
                </div>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                </div>
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={formData.password}
                  onChange={handleInputChange}
                  className={`block w-full pl-10 pr-10 py-3 rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                    errors.password ? 'ring-2 ring-red-500' : ''
                  }`}
                  style={{
                    backgroundColor: colors.muted,
                    border: `1px solid ${errors.password ? '#ef4444' : colors.border}`,
                    color: colors.foreground
                  }}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center hover:opacity-80"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                  ) : (
                    <Eye className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                  )}
                </button>
              </div>
              {errors.password && (
                <div className="mt-1 flex items-center text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.password}
                </div>
              )}
            </div>

            {/* Remember Me & Forgot Password */}
            {/* <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="rememberMe"
                  name="rememberMe"
                  type="checkbox"
                  checked={formData.rememberMe}
                  onChange={handleInputChange}
                  className="h-4 w-4 rounded"
                  style={{
                    accentColor: colors.primary,
                    backgroundColor: colors.muted,
                    borderColor: colors.border
                  }}
                />
                <label htmlFor="rememberMe" className="ml-2 block text-sm" style={{ color: colors.foreground }}>
                  Remember me
                </label>
              </div>
              <button
                type="button"
                className="text-sm font-medium hover:opacity-80"
                style={{ color: colors.primary }}
                onClick={() => alert('Password reset functionality would go here')}
              >
                Forgot password?
              </button>
            </div> */}

            {/* General Error Message */}
            {errors.general && (
              <div className="flex items-center text-red-400 text-sm p-3 rounded-lg" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
                <AlertCircle className="h-4 w-4 mr-2" />
                {errors.general}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isLoading}
              className={`w-full flex justify-center py-3 px-4 rounded-lg shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors ${
                isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90'
              }`}
              style={{ 
                backgroundColor: colors.primary,
                focusRingColor: colors.primary,
                focusRingOffsetColor: colors.card
              }}
            >
              {isLoading ? (
                <div className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Signing in...
                </div>
              ) : (
                'Sign in'
              )}
            </button>
          </div>

          {/* Divider */}
          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t" style={{ borderColor: colors.border }} />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 text-sm" style={{ backgroundColor: `${colors.card}CC`, color: colors.mutedForeground }}>
                  New to our platform?
                </span>
              </div>
            </div>
          </div>

          {/* Demo and Sign up links */}
          <div className="mt-6 text-center space-y-3">
            <button
              type="button"
              className="w-full py-2 px-4 rounded-lg font-medium text-sm hover:opacity-90 transition-colors"
              style={{
                backgroundColor: colors.accent,
                color: 'white'
              }}
              onClick={() => {
                // Use the secure demo login function
                loginDemo();
                // Redirect directly to activities page
                router.push('/activities');
              }}
            >
              Try Demo →
            </button>

            <button
              type="button"
              className="font-medium text-sm hover:opacity-80 transition-colors"
              style={{ color: colors.accent }}
              onClick={() => router.push('/register')}
            >
              Sign up →
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-sm mt-6" style={{ color: colors.mutedForeground }}>
          <p>Secure login with enterprise-grade encryption</p>
        </div>
      </div>

      <style jsx>{`
        input:focus {
          ring: 2px solid ${colors.primary};
        }
        
        input::placeholder {
          color: ${colors.mutedForeground};
          opacity: 0.7;
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
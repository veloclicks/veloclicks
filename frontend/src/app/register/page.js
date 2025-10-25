'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, User, Mail, Lock, AlertCircle, Check } from 'lucide-react';

const RegistrationPage = () => {
  const router = useRouter();
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
    agreeTerms: false,
    agreeNewsletter: false
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);

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
    
    if (!formData.firstName.trim()) {
      newErrors.firstName = 'First name is required';
    }
    
    if (!formData.lastName.trim()) {
      newErrors.lastName = 'Last name is required';
    }
    
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(formData.password)) {
      newErrors.password = 'Password must contain uppercase, lowercase, and number';
    }
    
    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    
    if (!formData.agreeTerms) {
      newErrors.agreeTerms = 'You must agree to the Terms of Service';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.email, // Using email as username
          email: formData.email,
          password: formData.password,
          firstname: formData.firstName,
          lastname: formData.lastName,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        alert('Registration successful! Please log in.');
        router.push('/login');
      } else {
        // Show error message
        setErrors({ general: data.message || 'Registration failed' });
      }
    } catch (error) {
      console.error('Registration error:', error);
      setErrors({ general: 'Network error. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  const getPasswordStrength = () => {
    const password = formData.password;
    if (!password) return { strength: 0, label: '' };
    
    let strength = 0;
    let label = '';
    
    if (password.length >= 8) strength += 1;
    if (/[a-z]/.test(password)) strength += 1;
    if (/[A-Z]/.test(password)) strength += 1;
    if (/\d/.test(password)) strength += 1;
    if (/[^A-Za-z0-9]/.test(password)) strength += 1;
    
    switch (strength) {
      case 0:
      case 1:
        label = 'Weak';
        break;
      case 2:
      case 3:
        label = 'Medium';
        break;
      case 4:
      case 5:
        label = 'Strong';
        break;
      default:
        label = '';
    }
    
    return { strength, label };
  };

  const passwordStrength = getPasswordStrength();

  return (
    <div className="min-h-screen relative flex items-center justify-center px-4 sm:px-6 lg:px-8 py-8">
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

      {/* Registration Form */}
      <div className="relative z-10 max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2" style={{ color: colors.foreground }}>
            Create Account
          </h2>
          <p className="text-sm" style={{ color: colors.mutedForeground }}>
            Join thousands of athletes tracking their performance
          </p>
        </div>

        {/* Form Card */}
        <div 
          className="p-8 rounded-xl shadow-2xl backdrop-blur-sm"
          style={{ 
            backgroundColor: `${colors.card}CC`, // Semi-transparent
            border: `1px solid ${colors.border}`
          }}
        >
          <div className="space-y-5">
            {/* Name Fields */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="firstName" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                  First Name
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                  </div>
                  <input
                    id="firstName"
                    name="firstName"
                    type="text"
                    value={formData.firstName}
                    onChange={handleInputChange}
                    className={`block w-full pl-10 pr-3 py-3 rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                      errors.firstName ? 'ring-2 ring-red-500' : ''
                    }`}
                    style={{
                      backgroundColor: colors.muted,
                      border: `1px solid ${errors.firstName ? '#ef4444' : colors.border}`,
                      color: colors.foreground
                    }}
                    placeholder="John"
                  />
                </div>
                {errors.firstName && (
                  <div className="mt-1 flex items-center text-red-400 text-xs">
                    <AlertCircle className="h-3 w-3 mr-1" />
                    {errors.firstName}
                  </div>
                )}
              </div>

              <div>
                <label htmlFor="lastName" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                  Last Name
                </label>
                <input
                  id="lastName"
                  name="lastName"
                  type="text"
                  value={formData.lastName}
                  onChange={handleInputChange}
                  className={`block w-full px-3 py-3 rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                    errors.lastName ? 'ring-2 ring-red-500' : ''
                  }`}
                  style={{
                    backgroundColor: colors.muted,
                    border: `1px solid ${errors.lastName ? '#ef4444' : colors.border}`,
                    color: colors.foreground
                  }}
                  placeholder="Doe"
                />
                {errors.lastName && (
                  <div className="mt-1 flex items-center text-red-400 text-xs">
                    <AlertCircle className="h-3 w-3 mr-1" />
                    {errors.lastName}
                  </div>
                )}
              </div>
            </div>

            {/* Email Field */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                Email address
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
                    color: colors.foreground
                  }}
                  placeholder="john@example.com"
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
              
              {/* Password Strength Indicator */}
              {formData.password && (
                <div className="mt-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs" style={{ color: colors.mutedForeground }}>
                      Password strength
                    </span>
                    <span className="text-xs font-medium" style={{ 
                      color: passwordStrength.strength >= 4 ? colors.chart3 : 
                             passwordStrength.strength >= 2 ? colors.accent : '#ef4444' 
                    }}>
                      {passwordStrength.label}
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-1">
                    <div 
                      className="h-1 rounded-full transition-all duration-300"
                      style={{ 
                        width: `${(passwordStrength.strength / 5) * 100}%`,
                        backgroundColor: passwordStrength.strength >= 4 ? colors.chart3 : 
                                       passwordStrength.strength >= 2 ? colors.accent : '#ef4444'
                      }}
                    ></div>
                  </div>
                </div>
              )}
              
              {errors.password && (
                <div className="mt-1 flex items-center text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.password}
                </div>
              )}
            </div>

            {/* Confirm Password Field */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium mb-2" style={{ color: colors.foreground }}>
                Confirm Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                </div>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  className={`block w-full pl-10 pr-10 py-3 rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                    errors.confirmPassword ? 'ring-2 ring-red-500' : ''
                  }`}
                  style={{
                    backgroundColor: colors.muted,
                    border: `1px solid ${errors.confirmPassword ? '#ef4444' : colors.border}`,
                    color: colors.foreground
                  }}
                  placeholder="Confirm your password"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center hover:opacity-80"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                  ) : (
                    <Eye className="h-5 w-5" style={{ color: colors.mutedForeground }} />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <div className="mt-1 flex items-center text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.confirmPassword}
                </div>
              )}
            </div>

            {/* Checkboxes */}
            <div className="space-y-3">
              <div className="flex items-start">
                <input
                  id="agreeTerms"
                  name="agreeTerms"
                  type="checkbox"
                  checked={formData.agreeTerms}
                  onChange={handleInputChange}
                  className="h-4 w-4 rounded mt-0.5"
                  style={{ 
                    accentColor: colors.primary,
                    backgroundColor: colors.muted,
                    borderColor: colors.border
                  }}
                />
                <label htmlFor="agreeTerms" className="ml-2 block text-sm leading-5" style={{ color: colors.foreground }}>
                  I agree to the{' '}
                  <button type="button" className="underline hover:opacity-80" style={{ color: colors.primary }}>
                    Terms of Service
                  </button>{' '}
                  and{' '}
                  <button type="button" className="underline hover:opacity-80" style={{ color: colors.primary }}>
                    Privacy Policy
                  </button>
                </label>
              </div>
              {errors.agreeTerms && (
                <div className="flex items-center text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.agreeTerms}
                </div>
              )}

              <div className="flex items-start">
                <input
                  id="agreeNewsletter"
                  name="agreeNewsletter"
                  type="checkbox"
                  checked={formData.agreeNewsletter}
                  onChange={handleInputChange}
                  className="h-4 w-4 rounded mt-0.5"
                  style={{ 
                    accentColor: colors.chart3,
                    backgroundColor: colors.muted,
                    borderColor: colors.border
                  }}
                />
                <label htmlFor="agreeNewsletter" className="ml-2 block text-sm leading-5" style={{ color: colors.mutedForeground }}>
                  Send me training tips and product updates
                </label>
              </div>
            </div>

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
                  Creating Account...
                </div>
              ) : (
                'Create Account'
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
                  Already have an account?
                </span>
              </div>
            </div>
          </div>

          {/* Login link */}
          <div className="mt-6 text-center">
            <button
              type="button"
              className="font-medium text-sm hover:opacity-80 transition-colors"
              style={{ color: colors.accent }}
              onClick={() => router.push('/login')}
            >
              Sign in here →
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-sm mt-6" style={{ color: colors.mutedForeground }}>
          <p>Join the community of data-driven athletes</p>
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

export default RegistrationPage;

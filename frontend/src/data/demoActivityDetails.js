// Demo activity details data for activity detail pages
// Includes GPS coordinates for maps and elevation profiles

// Generate a realistic cycling route around London with elevation
const generateLondonRoute = () => {
  // Start point: Hyde Park Corner
  const startLat = 51.5045;
  const startLng = -0.1527;

  const points = [];
  const elevationProfile = [];

  // Create a route that goes through Hyde Park, Regent's Park, and back
  const waypoints = [
    { lat: 51.5045, lng: -0.1527, elevation: 30 }, // Hyde Park Corner
    { lat: 51.5074, lng: -0.1533, elevation: 35 }, // Hyde Park
    { lat: 51.5090, lng: -0.1537, elevation: 40 }, // Speaker's Corner
    { lat: 51.5105, lng: -0.1592, elevation: 45 }, // Marble Arch
    { lat: 51.5154, lng: -0.1587, elevation: 50 }, // Baker Street
    { lat: 51.5264, lng: -0.1541, elevation: 65 }, // Regent's Park
    { lat: 51.5311, lng: -0.1448, elevation: 70 }, // Camden
    { lat: 51.5287, lng: -0.1325, elevation: 75 }, // King's Cross
    { lat: 51.5225, lng: -0.1187, elevation: 45 }, // Gray's Inn
    { lat: 51.5174, lng: -0.1204, elevation: 40 }, // Holborn
    { lat: 51.5101, lng: -0.1288, elevation: 35 }, // Covent Garden
    { lat: 51.5074, lng: -0.1278, elevation: 30 }, // Trafalgar Square
    { lat: 51.5014, lng: -0.1419, elevation: 25 }, // Green Park
    { lat: 51.5045, lng: -0.1527, elevation: 30 }  // Back to start
  ];

  // Interpolate points between waypoints for smooth route
  for (let i = 0; i < waypoints.length - 1; i++) {
    const start = waypoints[i];
    const end = waypoints[i + 1];
    const segments = 8; // Reduced from 20 to 8 for smoother profile

    for (let j = 0; j <= segments; j++) {
      const ratio = j / segments;
      const lat = start.lat + (end.lat - start.lat) * ratio;
      const lng = start.lng + (end.lng - start.lng) * ratio;
      const elevation = start.elevation + (end.elevation - start.elevation) * ratio;

      // Reduced noise for smoother elevation profile
      const latNoise = (Math.random() - 0.5) * 0.0001;
      const lngNoise = (Math.random() - 0.5) * 0.0001;
      const elevationNoise = (Math.random() - 0.5) * 2; // Reduced from 5 to 2

      // Calculate realistic heart rate based on elevation and distance
      const baseHeartRate = 145; // Base effort level
      const elevationFactor = (elevation - 30) * 0.3; // Higher elevation = higher HR
      const effortVariation = Math.sin(ratio * Math.PI * 2) * 8; // Periodic effort changes
      const heartRate = Math.round(baseHeartRate + elevationFactor + effortVariation + (Math.random() - 0.5) * 6);

      // Ensure all values are valid numbers
      const finalElevation = Math.round(Math.max(0, elevation + elevationNoise) * 100) / 100;
      const finalHeartRate = Math.round(Math.max(100, Math.min(185, heartRate)));
      const finalDistance = Math.round((points.length * 0.1) * 100) / 100; // Round distance too

      points.push([lat + latNoise, lng + lngNoise]);
      elevationProfile.push({
        distance: finalDistance,
        elevation: finalElevation,
        heartrate: finalHeartRate,
        index: points.length
      });
    }
  }

  return { points, elevationProfile };
};

// Generate demo activity details for different activity IDs
const generateDemoActivityDetail = (activityId) => {
  const { points, elevationProfile } = generateLondonRoute();

  // Calculate total distance from elevation profile
  const totalDistance = elevationProfile[elevationProfile.length - 1]?.distance * 1000 || 25000; // Convert to meters

  // Calculate realistic metrics
  const elapsedTime = 3600 + Math.random() * 1800; // 1-1.5 hours
  const avgSpeed = totalDistance / elapsedTime; // m/s
  const maxSpeed = avgSpeed * 1.5;
  const avgPower = 150 + Math.random() * 50; // 150-200W
  const maxPower = avgPower * 1.8;
  const avgHeartRate = 140 + Math.random() * 20; // 140-160 bpm
  const maxHeartRate = avgHeartRate + 30;

  return {
    // Basic activity data
    activity: {
      id: parseInt(activityId),
      name: "London Parks Circuit",
      start_date_local: "2024-10-15T09:30:00",
      elapsed_time: Math.round(elapsedTime),
      moving_time: Math.round(elapsedTime * 0.9),
      distance: totalDistance,
      total_elevation_gain: Math.round(Math.max(...elevationProfile.map(p => p.elevation)) - Math.min(...elevationProfile.map(p => p.elevation))),
      average_speed: avgSpeed,
      max_speed: maxSpeed,
      average_watts: Math.round(avgPower),
      max_watts: Math.round(maxPower),
      weighted_average_watts: Math.round(avgPower * 1.05),
      average_heartrate: Math.round(avgHeartRate),
      max_heartrate: Math.round(maxHeartRate),
      suffer_score: Math.round(avgPower * elapsedTime / 3600 / 4), // Rough calculation
      description: "Beautiful morning ride through London's parks. Perfect weather and great training session!",
      type: "Ride",
      sport_type: "Ride"
    },

    // Route streams for map
    routeStreams: {
      latlng: {
        data: points,
        series_type: "distance",
        original_size: points.length,
        resolution: "high"
      },
      elevationProfile: {
        profile_data: elevationProfile
      }
    }
  };
};

// Export function to get demo activity details by ID
export const getDemoActivityDetails = (activityId) => {
  // For demo purposes, we'll generate the same route but can vary it by ID if needed
  return generateDemoActivityDetail(activityId);
};
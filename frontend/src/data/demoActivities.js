// Demo activities data for the demo user
// 20 activities per year from 2018-2025 with realistic cycling data

const generateDemoActivities = () => {
  const activities = [];
  const years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];

  const activityNames = [
    'Morning Training Ride', 'Evening Intervals', 'Weekend Long Ride', 'Hill Climb Session',
    'Recovery Ride', 'Time Trial Practice', 'Group Ride', 'Endurance Training',
    'Sprint Intervals', 'Base Training', 'Threshold Session', 'Tempo Ride',
    'Climbing Practice', 'Cycling Commute', 'Race Simulation', 'Easy Spin',
    'Power Training', 'Cadence Work', 'Fartlek Training', 'Social Ride'
  ];

  let activityId = 1000000; // Start with a high ID to avoid conflicts

  years.forEach(year => {
    for (let i = 0; i < 20; i++) {
      // Randomly distribute activities across the year
      const month = months[Math.floor(Math.random() * 12)];
      const day = String(Math.floor(Math.random() * 28) + 1).padStart(2, '0');
      const hour = Math.floor(Math.random() * 12) + 7; // 7 AM to 6 PM
      const minute = Math.floor(Math.random() * 60);

      // Random duration between 25 minutes (1500s) and 1hr 35min (5700s)
      const elapsedTime = Math.floor(Math.random() * (5700 - 1500) + 1500);
      const elapsedTimeMinutes = Math.round(elapsedTime / 60);

      // Random distance based on duration (assume 25-35 km/h average speed)
      const avgSpeed = (Math.random() * 10 + 25) / 3.6; // 25-35 km/h converted to m/s
      const distance = Math.round(avgSpeed * elapsedTime);

      // Random power between 100W and 210W
      const avgPower = Math.floor(Math.random() * 110 + 100);
      const normalisedPower = Math.floor(avgPower * (0.95 + Math.random() * 0.1)); // +/- 5% of avg

      // Random elevation gain (more for longer rides)
      const elevationGain = Math.floor((elapsedTime / 3600) * (200 + Math.random() * 400));

      const activity = {
        id: activityId++,
        name: activityNames[i % activityNames.length] + ` (${year})`,
        dateTime: `${year}-${month}-${day}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00Z`,
        elapsedTime: elapsedTimeMinutes,
        distance: distance,
        avgSpeed: avgSpeed,
        elevationGain: elevationGain,
        avgPower: avgPower,
        normalisedPower: normalisedPower,
        // Additional fields that might be used
        start_date_local: `${year}-${month}-${day}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`,
        elapsed_time: elapsedTime,
        average_speed: avgSpeed,
        total_elevation_gain: elevationGain,
        average_watts: avgPower,
        weighted_average_watts: normalisedPower
      };

      activities.push(activity);
    }
  });

  // Sort by date (newest first)
  return activities.sort((a, b) => new Date(b.dateTime) - new Date(a.dateTime));
};

export const demoActivitiesData = generateDemoActivities();
import "./globals.css";
import { AuthProvider } from '../contexts/AuthContext';
import { ActivitySyncProvider } from '../contexts/ActivitySyncContext';

export const metadata = {
  title: "Veloclicks",
  description: "Training data analytics",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <ActivitySyncProvider>{children}</ActivitySyncProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

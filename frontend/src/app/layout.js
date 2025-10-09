import "./globals.css";
import { AuthProvider } from '../contexts/AuthContext';

export const metadata = {
  title: "Veloclicks",
  description: "Training data analytics",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}

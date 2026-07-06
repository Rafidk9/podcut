import "./globals.css";

export const metadata = {
  title: "PodCut — AI video editor",
  description: "Two-camera podcast switching + filler removal",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

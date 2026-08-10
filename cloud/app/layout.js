import "./globals.css";

export const metadata = {
  title: "PodCut",
  description: "Queue and watch reel renders. The laptop does the work.",
};

export const viewport = {
  themeColor: "#0a0c11",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

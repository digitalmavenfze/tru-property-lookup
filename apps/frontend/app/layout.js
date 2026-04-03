export const metadata = {
  title: "Tru Property Lookup",
  description: "Dubai property owner and unit lookup platform"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "Arial, sans-serif", background: "#f7f7f7" }}>
        {children}
      </body>
    </html>
  );
}

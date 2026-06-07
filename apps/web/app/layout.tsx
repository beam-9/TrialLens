import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TrialLens | Biomedical Evidence Intelligence",
  description:
    "Explore biomedical literature, clinical trials, and FDA records through a citation-first research workspace.",
  keywords: ["biomedical evidence", "clinical trials", "PubMed", "openFDA", "RAG", "AI research assistant"],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

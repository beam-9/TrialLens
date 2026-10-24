import type { Metadata } from "next";
import "./globals.css";
import { Geist } from "next/font/google";
import { cookies } from "next/headers";
import { cn } from "@/lib/utils";
import { TooltipProvider } from "@/components/ui/tooltip";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

const directionContract = `<!--
THESIS: TrialLens is an evidence registry for everyday research, replacing the marketing hero with a working evidence-first dashboard.
OWN-WORLD: Near-white and cool-gray surfaces, graphite Geist typography, one restrained teal action color, thin separators and compact controls.
STORY: Create or reopen a research topic, inspect extracted evidence, ask scoped questions, and collect chosen answers in Brief.
FIRST VIEWPORT: A 72px desktop header holds the compact builder; a 216px left index keeps five views and stable workspace order; source inventory sits beside the dominant evidence table. Mobile uses a 64px header and disclosed builder.
FORM: Evidence Registry, user-approved composition A; grounded direction 6, seed 7c7f8aa4. Selection highlights travel between stable entries; brief content transitions respect reduced motion.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`;

export const metadata: Metadata = {
  title: "TrialLens | Biomedical Evidence Workspace",
  description:
    "Explore PubMed papers, ClinicalTrials.gov records, and FDA data through inspectable evidence rows and cited synthesis.",
  keywords: [
    "biomedical evidence workspace",
    "clinical trials AI",
    "PubMed research assistant",
    "openFDA evidence",
    "RAG evaluation",
    "AI portfolio project",
  ],
  openGraph: {
    title: "TrialLens | Biomedical Evidence Workspace",
    description:
      "Explore biomedical literature, clinical trials, and FDA records through structured evidence tables and citation-backed answers.",
    type: "website",
  },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const savedTheme = (await cookies()).get("triallens.theme")?.value;

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn("font-sans", geist.variable, savedTheme === "dark" && "dark", savedTheme === "light" && "light")}
    >
      <body>
        <span hidden aria-hidden="true" dangerouslySetInnerHTML={{ __html: directionContract }} />
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}

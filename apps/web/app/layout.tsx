import type { Metadata } from "next";
import "./globals.css";
import { Geist, League_Gothic } from "next/font/google";
import { cookies } from "next/headers";
import { cn } from "@/lib/utils";
import { TooltipProvider } from "@/components/ui/tooltip";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
const leagueGothic = League_Gothic({ subsets: ["latin"], variable: "--font-display" });

const directionContract = `<!--
THESIS: Evidence becomes trustworthy when its path stays visible. This surface refuses the atmospheric research dashboard and makes provenance the composition.
OWN-WORLD: Cool mineral surfaces, graphite type, one teal signal, softly irregular flow fields, precise rules, and compact research controls.
STORY: Define a research focus, watch four source families converge, inspect extraction rows, then ask a cited question without losing uncertainty or source context.
FIRST VIEWPORT: A slim utility header sits above a diagonal evidence current. The headline anchors the left, the workspace launcher occupies the central flow zone, and the application shell rises immediately below.
FORM: Evidence Ribbon, approved composition C, seed key 18d19925.
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
      className={cn("font-sans", geist.variable, leagueGothic.variable, savedTheme === "dark" && "dark", savedTheme === "light" && "light")}
    >
      <body>
        <span hidden aria-hidden="true" dangerouslySetInnerHTML={{ __html: directionContract }} />
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}

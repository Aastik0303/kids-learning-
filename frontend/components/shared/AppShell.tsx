"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AvatarDock } from "@/components/avatar/AvatarDock";
import { pathAccents, pathSummaries } from "@/data/prototype";
import { clearSession, getOrCreateGuestChild, getUser, isGuestSession } from "@/services/session";
import type { ChildProfile, User } from "@/types";

function progressPercent(child: ChildProfile, pathId: string) {
  const progress = child.path_progress[pathId];
  const total = pathSummaries.find((path) => path.path_id === pathId)?.total_stages ?? 8;
  return Math.round(((progress?.completed_stages.length ?? 0) / total) * 100);
}

function ParentDrawer({
  child,
  user,
  guest,
  onClose
}: {
  child: ChildProfile | null;
  user: User | null;
  guest: boolean;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-ink/35 backdrop-blur-sm" role="dialog" aria-modal="true">
      <button className="absolute inset-0 h-full w-full cursor-default" aria-label="Close parent profile" onClick={onClose} />
      <aside
        data-surface="parent"
        className="absolute right-0 top-0 grid h-full w-full max-w-md content-start gap-4 overflow-y-auto bg-[#fbfcf6] p-5 shadow-soft sm:rounded-l-[2rem]"
      >
        <div className="surface-panel flex items-center justify-between gap-3 rounded-[2rem] p-4">
          <div>
            <p className="text-sm font-black uppercase text-leaf">Parent Profile</p>
            <h2 className="text-3xl font-black text-ink">{guest ? "Guest session" : user?.name ?? "Parent"}</h2>
          </div>
          <button className="pressable rounded-full bg-ink px-4 py-3 font-black text-white shadow-soft" onClick={onClose}>
            Close
          </button>
        </div>

        {guest ? (
          <div className="grid gap-4">
            <div className="lift-card rounded-[2rem] p-5">
              <h3 className="text-2xl font-black text-ink">Create a parent account</h3>
              <p className="mt-2 font-bold text-ink/70">Create a parent account to save progress, rewards, and certificates.</p>
            </div>
            <Link className="pressable rounded-3xl bg-leaf px-5 py-4 text-center text-xl font-black text-white shadow-soft" href="/signup">
              Sign Up
            </Link>
            <Link className="pressable rounded-3xl bg-white px-5 py-4 text-center text-xl font-black text-ink shadow-soft" href="/login">
              Parent Login
            </Link>
          </div>
        ) : child ? (
          <div className="grid gap-4">
            <div className="lift-card rounded-[2rem] p-5">
              <p className="font-black text-leaf">Child profile</p>
              <h3 className="mt-1 text-3xl font-black text-ink">{child.name}</h3>
              <p className="mt-2 font-bold text-ink/70">Age Group: {child.age_group}</p>
              <p className="font-bold text-ink/70">Language: {child.preferred_language}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-[2rem] bg-sunshine p-5 shadow-soft">
                <p className="font-black text-ink/70">Stars</p>
                <p className="text-4xl font-black text-ink">{child.stars}</p>
              </div>
              <div className="lift-card rounded-[2rem] p-5">
                <p className="font-black text-ink/70">Certificate</p>
                <p className="text-xl font-black text-ink">{child.certificate_unlocked ? "Unlocked" : "Waiting"}</p>
              </div>
            </div>

            <section className="lift-card grid gap-3 rounded-[2rem] p-5">
              <h3 className="text-2xl font-black text-ink">Learning Progress</h3>
              {["numbers", "alphabets", "colours", "shapes"].map((pathId) => {
                const percent = progressPercent(child, pathId);
                return (
                  <div key={pathId} className="grid gap-2">
                    <div className="flex items-center justify-between gap-3 font-black">
                      <span>{pathAccents[pathId].label}</span>
                      <span>{percent}%</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${percent}%` }} />
                    </div>
                  </div>
                );
              })}
            </section>

            <button
              className="pressable rounded-3xl bg-ink px-5 py-4 text-xl font-black text-white shadow-soft"
              onClick={() => {
                clearSession();
                window.location.href = "/";
              }}
            >
              Logout
            </button>
          </div>
        ) : null}
      </aside>
    </div>
  );
}

export function AppShell({ children, title = "Little Learning" }: { children: React.ReactNode; title?: string }) {
  const pathname = usePathname();
  const [child, setChild] = useState<ChildProfile | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [guest, setGuest] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const sync = () => {
      setChild(getOrCreateGuestChild());
      setUser(getUser());
      setGuest(isGuestSession());
    };
    sync();
    window.addEventListener("little-learning-session", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("little-learning-session", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const navItems = [
    { href: "/", label: "🏠 Home", guideId: "go-home" },
    { href: "/practice", label: "🎨 Practice", guideId: "start-practice" },
    { href: "/levels", label: "🗺️ Adventure", guideId: "continue-adventure" },
    { href: "/rewards", label: "🎁 Rewards", guideId: "open-rewards" },
    { href: "/word-coach", label: "🔤 Word Coach", guideId: "word-coach" },
    { href: "/sentence-coach", label: "📖 Sentence Coach", guideId: "sentence-coach" }
  ];

  return (
    // data-surface drives the touch-target floors in globals.css. This shell
    // wraps the child-facing routes, so the 64px learning floor applies inside
    // it — except within nested surfaces: the header and the guide dock mark
    // themselves "chrome" (44px) and the parent drawer marks itself "parent".
    //
    // Bottom padding is NOT a fixed pb-36 any more. The dock measures itself
    // and publishes --dock-height, so the reserved space always matches the
    // real dock instead of a guess that goes stale the moment it reflows.
    <main data-surface="child" className="app-shell-main mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 pt-4 sm:px-6">
      <header data-surface="chrome" className="nav-shell no-print sticky top-3 z-40 mb-5 rounded-[2rem] px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-3 text-xl font-black text-ink">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-leaf text-white shadow-soft">LL</span>
            <span className="grid leading-tight">
              <span>{title}</span>
              <span className="text-xs font-black uppercase text-ink/45">Nursery Studio</span>
            </span>
          </Link>
          {/* Desktop chrome only. A pre-literate child does not navigate by a
              six-item text menu — they are led by the guide and the adventure
              screen (docs/ops/OP-03-entry-flow.md §5). Below md these six pills
              wrapped to three rows and filled the entire first screen. */}
          <nav className="hidden flex-wrap items-center gap-2 text-sm font-black md:flex">
            {navItems.map((item) => {
              const active = item.href === "/" ? pathname === "/" || pathname === "/home" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  data-guide-id={item.guideId}
                  className={`pressable rounded-full px-4 py-3 transition ${active ? "bg-ink text-white" : "bg-[#f5f8ef] text-ink hover:bg-sunshine/30"}`}
                  href={item.href}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-sunshine px-4 py-3 text-sm font-black text-ink shadow-soft">⭐ {child?.stars ?? 0}</span>
            {guest ? (
              <Link className="pressable hidden rounded-full bg-leaf px-4 py-3 text-sm font-black text-white shadow-soft sm:inline-flex" href="/signup">
                Sign Up
              </Link>
            ) : null}
            <button data-guide-id="parent-profile" className="pressable rounded-full bg-white px-4 py-3 text-sm font-black text-ink shadow-soft" onClick={() => setDrawerOpen(true)}>
              {guest ? "Parent Login" : `${user?.name.split(" ")[0] ?? "Parent"} Profile`}
            </button>
          </div>
        </div>
      </header>
      {children}
      <AvatarDock />
      {drawerOpen ? <ParentDrawer child={child} user={user} guest={guest} onClose={() => setDrawerOpen(false)} /> : null}
    </main>
  );
}

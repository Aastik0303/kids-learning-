"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AvatarDock } from "@/components/avatar/AvatarDock";
import { ScheduleStrip } from "@/components/shared/ScheduleStrip";
import { useActiveChild } from "@/lib/useActiveChild";
import { getClassForChild } from "@/services/curriculum";
import { logout } from "@/services/auth";
import { clearSession, getToken, getUser, isGuestSession } from "@/services/session";
import type { ChildProfile, ClassDetail, User } from "@/types";

function progressPercent(child: ChildProfile, subjectId: string, topicCount: number) {
  const done = child.subject_progress?.[subjectId]?.completed_topics.length ?? 0;
  return topicCount ? Math.round((done / topicCount) * 100) : 0;
}

/** Sign out of the server as well as this browser, then start again at home. */
async function signOut() {
  const token = getToken();
  if (token) await logout(token);
  clearSession();
  window.location.href = "/";
}

function ParentDrawer({
  child,
  detail,
  user,
  guest,
  onClose
}: {
  child: ChildProfile | null;
  detail: ClassDetail | null;
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
              <p className="mt-2 font-bold text-ink/70">Class: {detail?.title ?? child.class_id}</p>
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
              {/* Subject names come from the manifest, never from a local list. */}
              {(detail?.subjects ?? []).map((subject) => {
                const percent = progressPercent(child, subject.subject_id, subject.topic_count);
                return (
                  <div key={subject.subject_id} className="grid gap-2">
                    <div className="flex items-center justify-between gap-3 font-black">
                      <span>{subject.title}</span>
                      <span>{percent}%</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${percent}%` }} />
                    </div>
                  </div>
                );
              })}
            </section>

            <Link
              className="pressable rounded-3xl bg-white px-5 py-4 text-center text-xl font-black text-ink shadow-soft"
              href="/parent/profile"
            >
              Class &amp; profile settings
            </Link>

            <button
              className="pressable rounded-3xl bg-ink px-5 py-4 text-xl font-black text-white shadow-soft"
              onClick={() => {
                void signOut();
              }}
            >
              Logout
            </button>
          </div>
        ) : (
          // Signed in, but no child loaded yet. Without this branch the drawer
          // opened completely empty, which read as a broken screen rather than
          // "there is nothing here yet".
          <div className="grid gap-4">
            <div className="lift-card rounded-[2rem] p-5">
              <h3 className="text-2xl font-black text-ink">No child profile yet</h3>
              <p className="mt-2 font-bold text-ink/70">
                Add a child to see their class, subjects and progress here.
              </p>
            </div>
            <Link
              className="pressable rounded-3xl bg-leaf px-5 py-4 text-center text-xl font-black text-white shadow-soft"
              href="/onboarding"
            >
              Add a child
            </Link>
            <button
              className="pressable rounded-3xl bg-ink px-5 py-4 text-xl font-black text-white shadow-soft"
              onClick={() => {
                void signOut();
              }}
            >
              Logout
            </button>
          </div>
        )}
      </aside>
    </div>
  );
}

export function AppShell({ children, title = "Saksham IQ" }: { children: React.ReactNode; title?: string }) {
  const pathname = usePathname();
  // The shell shares one source of truth with the pages inside it, so the
  // header, the drawer and the page can never disagree about who is signed in.
  const { child } = useActiveChild();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [guest, setGuest] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  // A popover that outlives the screen it was opened on is a bug a child will
  // find in seconds, so it closes with the route.
  useEffect(() => {
    setMoreOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!child) {
      setDetail(null);
      return;
    }
    getClassForChild(child.child_id).then(setDetail).catch(() => setDetail(null));
  }, [child]);

  useEffect(() => {
    const sync = () => {
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

  // Three destinations, and the first one is where the app already is: opening
  // the site lands on the class, so this row is about the two places a child
  // goes *away* to. Home and the conductor's own `/class` were both doors into
  // a lesson, and there is one lesson now — `/` and `/class` both open the AI
  // Teacher, so offering them as separate tabs would be three names for one
  // room. Practice went the same way and is still reachable by URL.
  const navItems = [
    // Today's class. It takes no topic: which levels are played today is the
    // frozen daily plan's decision, so there is nothing to choose on the way in.
    { href: "/ai-teacher", label: "🧑‍🏫 Class", icon: "🧑‍🏫", short: "Class", guideId: "ai-teacher", primary: true },
    // The map. It teaches nothing — it is where a child sees the levels their
    // class has opened and what is still asleep.
    { href: "/adventure", label: "🗺️ My Levels", icon: "🗺️", short: "Levels", guideId: "continue-adventure", primary: true },
    { href: "/rewards", label: "🎁 Rewards", icon: "🎁", short: "Rewards", guideId: "open-rewards", primary: true }
  ];

  // What the More sheet would hold: the tabs that do not fit the phone row, and
  // the sign-up a guest is offered.
  const hasMore = navItems.some((item) => !item.primary) || guest;

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname === "/home" : pathname.startsWith(href);

  // The touch-target floor follows the class's experience mode: `early`
  // (Play Group, Nursery) raises learning controls to 96px, `standard` keeps
  // them at 64px. Both come from the manifest, not from an age test here.
  const surface = detail?.experience.mode_id === "early" ? "early" : "child";

  return (
    // data-surface drives the touch-target floors in globals.css. This shell
    // wraps the child-facing routes, so the 64px learning floor applies inside
    // it — except within nested surfaces: the header and the guide dock mark
    // themselves "chrome" (44px) and the parent drawer marks itself "parent".
    //
    // Bottom padding is NOT a fixed pb-36 any more. The dock measures itself
    // and publishes --dock-height, so the reserved space always matches the
    // real dock instead of a guess that goes stale the moment it reflows.
    <main data-surface={surface} data-experience-mode={detail?.experience.mode_id ?? "standard"} className="app-shell-main mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 pt-4 sm:px-6">
      <header data-surface="chrome" className="nav-shell no-print sticky top-3 z-40 mb-5 rounded-[2rem] px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-3 text-xl font-black text-ink">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-leaf text-white shadow-soft">SI</span>
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
              const active = isActive(item.href);
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
      {/* The day's plan, on every screen and not only where a lesson is. The
          class is built stage-for-item out of it, so it is the rule the child
          is living inside rather than a page's decoration. */}
      <ScheduleStrip />
      {children}
      <AvatarDock />

      {/* Phone navigation. The header row is desktop-only, which left a phone
          with no way to reach Practice, Rewards or the coaches from anywhere
          but the home screen. This is a thumb-reachable bar instead of a menu:
          four pictures a child can aim at, with the two coaches behind More so
          the row stays wide enough to hit. It is chrome, so it keeps the 44px
          floor rather than the learning floor, and the guide dock is lifted by
          its height in globals.css so the two never sit on top of each other. */}
      <nav data-surface="chrome" className="mobile-tabs no-print" aria-label="Main navigation">
        {navItems
          .filter((item) => item.primary)
          .map((item) => (
            <Link
              key={item.href}
              href={item.href}
              data-guide-id={item.guideId}
              data-active={isActive(item.href) ? "true" : undefined}
              aria-current={isActive(item.href) ? "page" : undefined}
              className="mobile-tab"
            >
              <span aria-hidden className="mobile-tab-icon">
                {item.icon}
              </span>
              <span className="mobile-tab-label">{item.short}</span>
            </Link>
          ))}

        {/* Only when there is something behind it. The row is three tabs now,
            and a More button that opens an empty sheet is a promise the app
            cannot keep. */}
        {hasMore ? (
          <button
            type="button"
            onClick={() => setMoreOpen((open) => !open)}
            aria-expanded={moreOpen}
            data-active={moreOpen ? "true" : undefined}
            className="mobile-tab"
          >
            <span aria-hidden className="mobile-tab-icon">
              {moreOpen ? "✕" : "✨"}
            </span>
            <span className="mobile-tab-label">More</span>
          </button>
        ) : null}

        {moreOpen ? (
          <div className="mobile-more">
            {navItems
              .filter((item) => !item.primary)
              .map((item) => (
                <Link key={item.href} href={item.href} data-guide-id={item.guideId} onClick={() => setMoreOpen(false)}>
                  {item.label}
                </Link>
              ))}
            {guest ? (
              <Link href="/signup" onClick={() => setMoreOpen(false)}>
                ✍️ Sign Up
              </Link>
            ) : null}
          </div>
        ) : null}
      </nav>

      {drawerOpen ? <ParentDrawer child={child} detail={detail} user={user} guest={guest} onClose={() => setDrawerOpen(false)} /> : null}
    </main>
  );
}

import { HomeExperience } from "@/components/home/HomeExperience";

// The age gate is gone. Age is asked once during onboarding and stored on the
// child; the class is resolved server-side from it and never re-asked here.
export default function Page() {
  return <HomeExperience />;
}

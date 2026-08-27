import { FrontDoor } from "@/components/home/FrontDoor";

// The age gate is gone. Age is asked once during onboarding and stored on the
// child; the class is resolved server-side from it and never re-asked here.
//
// And the front door no longer offers a menu: a signed-in child goes straight
// to their class, which runs today's frozen plan. See `FrontDoor`.
export default function Page() {
  return <FrontDoor />;
}

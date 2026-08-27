import { FrontDoor } from "@/components/home/FrontDoor";

// `/home` is the same door as `/`. Two hub screens that could drift apart is
// how a child ends up with two different ideas of where their lesson is.
export default function HomePage() {
  return <FrontDoor />;
}

import { redirect } from "next/navigation";

export default async function AdventureWorldPage({ params }: { params: Promise<{ pathId: string }> }) {
  const { pathId } = await params;
  redirect(`/levels/${pathId}`);
}

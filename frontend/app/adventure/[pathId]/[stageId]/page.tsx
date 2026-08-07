import { redirect } from "next/navigation";

export default async function AdventureLevelPage({ params }: { params: Promise<{ pathId: string; stageId: string }> }) {
  const { pathId, stageId } = await params;
  redirect(`/levels/${pathId}/${stageId}`);
}

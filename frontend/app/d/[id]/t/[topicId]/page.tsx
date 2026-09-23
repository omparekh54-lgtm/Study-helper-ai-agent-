import { TopicView } from "@/components/topic-view";

export default async function TopicPage({ params }: PageProps<"/d/[id]/t/[topicId]">) {
  const { id, topicId } = await params;
  return <TopicView documentId={id} topicId={topicId} />;
}

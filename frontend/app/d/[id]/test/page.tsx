import { MockTestView } from "@/components/mock-test-view";

export const metadata = { title: "Mock test" };

export default async function MockTestPage({ params }: PageProps<"/d/[id]/test">) {
  const { id } = await params;
  return <MockTestView documentId={id} />;
}

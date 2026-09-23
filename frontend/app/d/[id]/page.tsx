import { DocumentView } from "@/components/document-view";

export default async function DocumentPage({ params }: PageProps<"/d/[id]">) {
  const { id } = await params;
  return <DocumentView id={id} />;
}

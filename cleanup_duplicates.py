from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

COLLECTION_NAME = "knowledge_base"

OLD_DOCUMENTS = {
    "MQ SURE! Promotions.docx",
    "MQ SURE! Simplified Collections.docx",
}

client = QdrantClient(
    host="localhost",
    port=6333
)

deleted = 0

for filename in OLD_DOCUMENTS:

    print(f"Checking duplicates for: {filename}")

    # Delete points where:
    # source = old document
    # AND document_id is NOT the legacy filename
    #
    # These are the duplicate points created by the
    # first version of the reusable ingestion script.

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="source",
                    match=MatchValue(value=filename)
                )
            ]
        ),
        limit=1000,
        with_payload=True,
        with_vectors=False
    )

    duplicate_ids = []

    for point in points:

        payload = point.payload or {}

        if payload.get("document_id") != filename:
            duplicate_ids.append(point.id)

    if duplicate_ids:

        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=duplicate_ids
        )

        deleted += len(duplicate_ids)

        print(f"Deleted {len(duplicate_ids)} duplicate chunks.")

    else:
        print("No duplicates found.")


print()
print(f"Total duplicate chunks deleted: {deleted}")

info = client.get_collection(COLLECTION_NAME)

print(f"Current Qdrant points: {info.points_count}")
import json
from qdrant_client import QdrantClient

COLLECTION_NAME = "knowledge_base"

client = QdrantClient(
    host="localhost",
    port=6333
)

manifest = {}

offset = None

while True:

    points, next_offset = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=100,
        offset=offset,
        with_payload=True,
        with_vectors=False
    )

    for point in points:

        payload = point.payload or {}

        source = payload.get("source")

        if not source:
            continue

        if source not in manifest:
            manifest[source] = {
                "document_id": payload.get("document_id"),
                "points": []
            }

        manifest[source]["points"].append(point.id)

    if next_offset is None:
        break

    offset = next_offset


with open("qdrant_manifest.json", "w", encoding="utf-8") as file:
    json.dump(
        manifest,
        file,
        indent=4
    )

print("Manifest created successfully.")
print(f"Documents tracked: {len(manifest)}")

for source, data in manifest.items():
    print(
        f"{source}: "
        f"{len(data['points'])} chunks"
    )
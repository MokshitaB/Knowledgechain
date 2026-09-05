import os
import hashlib
import docx2txt

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


KNOWLEDGE_BASE = "knowledge_base"
COLLECTION_NAME = "knowledge_base"

client = QdrantClient(
    host="localhost",
    port=6333
)


def get_document_hash(filename):
    filepath = os.path.join(
        KNOWLEDGE_BASE,
        filename
    )

    text = docx2txt.process(filepath)

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


print("=" * 60)
print("       INITIALIZING DOCUMENT HASHES")
print("=" * 60)


# Get all DOCX files currently in the folder

files = [
    filename
    for filename in os.listdir(KNOWLEDGE_BASE)
    if filename.lower().endswith(".docx")
]


for filename in sorted(files):

    print(f"\nProcessing: {filename}")

    # --------------------------------------------------------
    # Calculate hash from current document
    # --------------------------------------------------------

    try:
        document_hash = get_document_hash(
            filename
        )

    except Exception as e:

        print(
            f"ERROR reading document: {e}"
        )

        continue

    # --------------------------------------------------------
    # Find all Qdrant points for this document
    # --------------------------------------------------------

    points = []

    offset = None

    while True:

        result = client.scroll(
            collection_name=COLLECTION_NAME,

            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(
                            value=filename
                        )
                    )
                ]
            ),

            limit=100,
            offset=offset,

            with_payload=True,
            with_vectors=False
        )

        batch, next_offset = result

        points.extend(batch)

        if next_offset is None:
            break

        offset = next_offset

    print(
        f"Qdrant chunks found: {len(points)}"
    )

    if not points:

        print(
            "⚠ No Qdrant points found. Skipping."
        )

        continue

    # --------------------------------------------------------
    # Add document_hash to ALL existing chunks
    # --------------------------------------------------------

    point_ids = [
        point.id
        for point in points
    ]

    client.set_payload(
        collection_name=COLLECTION_NAME,

        payload={
            "document_hash": document_hash
        },

        points=point_ids
    )

    print(
        "✓ Hash added to "
        f"{len(point_ids)} chunks"
    )


print("\n" + "=" * 60)
print("HASH INITIALIZATION COMPLETE")
print("=" * 60)

info = client.get_collection(
    COLLECTION_NAME
)

print(
    f"Total Qdrant points: "
    f"{info.points_count}"
)

print("=" * 60)
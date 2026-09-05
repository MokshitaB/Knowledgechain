import os
import hashlib
import uuid
import docx2txt
import requests

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Distance,
    VectorParams,
)


# ============================================================
# CONFIGURATION
# ============================================================

KNOWLEDGE_BASE = "knowledge_base"
COLLECTION_NAME = "knowledge_base"

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

EMBEDDING_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"

CHUNK_SIZE = 1000
OVERLAP = 200


# ============================================================
# CONNECT TO QDRANT
# ============================================================

print("=" * 60)
print("          KNOWLEDGE BASE INGESTION")
print("=" * 60)

client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)

collections = [
    collection.name
    for collection in client.get_collections().collections
]

if COLLECTION_NAME not in collections:

    print("\nCreating Qdrant collection...")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
        ),
    )

print("\nQdrant connection: OK")


# ============================================================
# CREATE DOCUMENT HASH
# ============================================================

def get_file_hash(text):
    """
    Creates a fingerprint of the document content.

    Same content  -> same hash
    Changed content -> different hash
    """

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# ============================================================
# GET ALL QDRANT POINTS FOR A DOCUMENT
# ============================================================

def get_qdrant_points_for_source(filename):

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
                        ),
                    )
                ]
            ),

            limit=100,
            offset=offset,

            with_payload=True,
            with_vectors=False,
        )

        batch, next_offset = result

        points.extend(batch)

        if next_offset is None:
            break

        offset = next_offset

    return points


# ============================================================
# DELETE ALL CHUNKS FOR A DOCUMENT
# ============================================================

def delete_document(filename):

    points = get_qdrant_points_for_source(
        filename
    )

    if not points:
        return 0

    point_ids = [
        point.id
        for point in points
    ]

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=point_ids,
    )

    return len(point_ids)


# ============================================================
# FIND DOCUMENTS IN LOCAL FOLDER
# ============================================================

files = sorted(
    filename
    for filename in os.listdir(KNOWLEDGE_BASE)
    if filename.lower().endswith(".docx")
)

print(
    f"\nDocuments found: {len(files)}"
)


# ============================================================
# GET DOCUMENT INFORMATION FROM QDRANT
# ============================================================

print("\nChecking existing documents...")

qdrant_documents = {}

offset = None

while True:

    result = client.scroll(
        collection_name=COLLECTION_NAME,

        limit=100,
        offset=offset,

        with_payload=True,
        with_vectors=False,
    )

    points, next_offset = result

    for point in points:

        payload = point.payload or {}

        source = payload.get("source")

        if not source:
            continue

        document_hash = payload.get(
            "document_hash"
        )

        if source not in qdrant_documents:

            qdrant_documents[source] = {
                "hashes": set(),
                "points": [],
            }

        qdrant_documents[source]["points"].append(
            point.id
        )

        if document_hash:

            qdrant_documents[source]["hashes"].add(
                document_hash
            )

    if next_offset is None:
        break

    offset = next_offset


print(
    f"Documents in Qdrant: "
    f"{len(qdrant_documents)}"
)


# ============================================================
# DELETE DOCUMENTS REMOVED FROM LOCAL FOLDER
# ============================================================

print("\nChecking for deleted documents...")

folder_files = set(files)

deleted_documents = 0

for source in list(qdrant_documents.keys()):

    if source not in folder_files:

        print(
            f"\n🗑️ Document removed from folder:"
        )

        print(source)

        removed = delete_document(
            source
        )

        print(
            f"✓ Removed {removed} Qdrant chunks"
        )

        deleted_documents += 1


# ============================================================
# PROCESS CURRENT DOCUMENTS
# ============================================================

new_documents = 0
updated_documents = 0
skipped_documents = 0
new_chunks = 0


for filename in files:

    print("\n" + "-" * 60)
    print(
        f"Document: {filename}"
    )

    filepath = os.path.join(
        KNOWLEDGE_BASE,
        filename,
    )

    # --------------------------------------------------------
    # READ DOCX
    # --------------------------------------------------------

    try:

        text = docx2txt.process(
            filepath
        )

    except Exception as e:

        print(
            f"ERROR reading document: {e}"
        )

        continue

    if not text.strip():

        print(
            "WARNING: Document is empty. Skipping."
        )

        continue

    # --------------------------------------------------------
    # CREATE HASH
    # --------------------------------------------------------

    document_hash = get_file_hash(
        text
    )

    # --------------------------------------------------------
    # CHECK EXISTING DOCUMENT
    # --------------------------------------------------------

    existing = qdrant_documents.get(
        filename
    )

    if existing:

        existing_hashes = existing[
            "hashes"
        ]

        # ----------------------------------------------------
        # UNCHANGED
        # ----------------------------------------------------

        if document_hash in existing_hashes:

            print(
                "✓ Document unchanged — skipped"
            )

            skipped_documents += 1

            continue

        # ----------------------------------------------------
        # MODIFIED
        # ----------------------------------------------------

        print(
            "🔄 Document changed — updating"
        )

        removed = delete_document(
            filename
        )

        print(
            f"✓ Removed {removed} old chunks"
        )

        updated_documents += 1

    else:

        # ----------------------------------------------------
        # NEW DOCUMENT
        # ----------------------------------------------------

        print(
            "➕ New document detected"
        )

        new_documents += 1

    # --------------------------------------------------------
    # SPLIT DOCUMENT INTO CHUNKS
    # --------------------------------------------------------

    chunks = []

    start = 0
    chunk_index = 0

    while start < len(text):

        end = start + CHUNK_SIZE

        chunk = text[start:end]

        if chunk.strip():

            chunks.append(
                {
                    "chunk": chunk,
                    "chunk_index": chunk_index,
                }
            )

            chunk_index += 1

        start += CHUNK_SIZE - OVERLAP

    print(
        f"Chunks created: {len(chunks)}"
    )

    # --------------------------------------------------------
    # GENERATE EMBEDDINGS
    # --------------------------------------------------------

    points = []

    for index, chunk_data in enumerate(
        chunks
    ):

        print(
            f"Embedding "
            f"{index + 1}/{len(chunks)}...",
            end="\r",
        )

        try:

            response = requests.post(
                EMBEDDING_URL,

                json={
                    "model": EMBEDDING_MODEL,
                    "input": chunk_data[
                        "chunk"
                    ],
                },

                timeout=120,
            )

            response.raise_for_status()

            data = response.json()

            embedding = data[
                "embeddings"
            ][0]

        except Exception as e:

            print(
                f"\nERROR generating embedding "
                f"for chunk {index}: {e}"
            )

            continue

        # ----------------------------------------------------
        # CREATE QDRANT POINT
        # ----------------------------------------------------

        points.append(
            PointStruct(
                id=str(
                    uuid.uuid4()
                ),

                vector=embedding,

                payload={
                    "chunk": chunk_data[
                        "chunk"
                    ],

                    "source": filename,

                    "document_hash":
                        document_hash,

                    "chunk_index":
                        chunk_data[
                            "chunk_index"
                        ],
                },
            )
        )

    print()

    # --------------------------------------------------------
    # UPLOAD TO QDRANT
    # --------------------------------------------------------

    if points:

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )

        print(
            f"✓ Added {len(points)} chunks "
            f"from {filename}"
        )

        new_chunks += len(points)

    else:

        print(
            "WARNING: No embeddings were generated."
        )


# ============================================================
# FINAL SUMMARY
# ============================================================

collection_info = client.get_collection(
    COLLECTION_NAME
)

print("\n" + "=" * 60)
print("                 INGESTION COMPLETE")
print("=" * 60)

print(
    f"New documents      : "
    f"{new_documents}"
)

print(
    f"Updated documents  : "
    f"{updated_documents}"
)

print(
    f"Skipped documents  : "
    f"{skipped_documents}"
)

print(
    f"Deleted documents  : "
    f"{deleted_documents}"
)

print(
    f"New chunks added   : "
    f"{new_chunks}"
)

print(
    f"Total Qdrant points: "
    f"{collection_info.points_count}"
)

print("=" * 60)
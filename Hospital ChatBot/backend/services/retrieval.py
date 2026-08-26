from pathlib import Path
import re


DOCUMENT_DIR = Path(__file__).resolve().parents[2] / "documents"


def load_documents():

    documents = []

    for file in DOCUMENT_DIR.glob("*.md"):

        text = file.read_text(
            encoding="utf-8"
        )

        documents.append({
            "filename": file.name,
            "content": text
        })

    return documents


def tokenize(text):

    return set(
        re.findall(
            r"\b[a-zA-Z]{3,}\b",
            text.lower()
        )
    )


def retrieve_documents(
    query: str,
    max_results: int = 3
):

    query_words = tokenize(query)

    documents = load_documents()

    scored = []

    for document in documents:

        document_words = tokenize(
            document["content"]
        )

        score = len(
            query_words.intersection(
                document_words
            )
        )

        scored.append(
            (
                score,
                document
            )
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    results = []

    for score, document in scored[:max_results]:

        if score > 0:

            results.append(
                f"""
SOURCE: {document['filename']}

{document['content']}
"""
            )

    return "\n\n".join(results)

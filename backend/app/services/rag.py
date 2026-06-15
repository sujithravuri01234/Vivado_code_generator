from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

from app.core.settings import settings
from app.services.supabase_store import CircuitRepository

try:
    from supabase import create_client
except Exception:  # pragma: no cover - optional dependency import guard
    create_client = None


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source: str
    title: str
    content: str
    tags: tuple[str, ...] = ()
    chunk_index: int = 0
    path: str = ""


class KnowledgeRetriever:
    def __init__(self, corpus_dir: str | None = None, top_k: int | None = None):
        self.corpus_dir = self._resolve_corpus_dir(corpus_dir or settings.rag_corpus_dir)
        self.top_k = top_k or settings.rag_top_k

    def search(self, query: str) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []

        candidates: list[dict[str, Any]] = []
        candidates.extend(self._search_supabase(query))
        candidates.extend(self._search_supabase_circuits(query))
        candidates.extend(self._search_local(query))
        candidates = self._dedupe_results(candidates)
        candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
        return candidates[: self.top_k]

    def _search_supabase(self, query: str) -> list[dict[str, Any]]:
        if not settings.supabase_url or not settings.supabase_key or create_client is None:
            return []

        client = create_client(settings.supabase_url, settings.supabase_key)
        match_function = settings.supabase_match_function

        for search_attempt in (self._rpc_vector_match, self._table_scan_match):
            try:
                result = search_attempt(client, query, match_function)
                if result:
                    return result
            except Exception:
                continue
        return []

    def _rpc_vector_match(self, client: Any, query: str, match_function: str) -> list[dict[str, Any]]:
        response = client.rpc(match_function, {"query_text": query, "match_count": self.top_k}).execute()
        data = getattr(response, "data", None) or []
        return self._normalize_rows(data, retriever="supabase-rpc")

    def _table_scan_match(self, client: Any, query: str, match_function: str) -> list[dict[str, Any]]:
        table = settings.supabase_knowledge_table
        response = (
            client.table(table)
            .select("id,source,title,content,tags,chunk_index,path")
            .limit(200)
            .execute()
        )
        data = getattr(response, "data", None) or []
        chunks = self._rows_to_chunks(data, fallback_source=table)
        return self._rank_chunks(query, chunks, retriever="supabase-table")

    def _search_local(self, query: str) -> list[dict[str, Any]]:
        chunks = self._load_local_chunks()
        return self._rank_chunks(query, chunks, retriever="local")

    def _search_supabase_circuits(self, query: str) -> list[dict[str, Any]]:
        if not settings.supabase_url or not settings.supabase_key:
            return []
        try:
            records = CircuitRepository().search_saved_circuits(query, top_k=self.top_k)
        except Exception:
            return []
        return records

    def _normalize_rows(self, rows: list[dict[str, Any]], retriever: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            tags_value = row.get("tags") or []
            if isinstance(tags_value, str):
                tags_value = [tag.strip() for tag in tags_value.split(",") if tag.strip()]
            normalized.append(
                {
                    "chunk_id": str(row.get("id") or row.get("chunk_id") or ""),
                    "source": str(row.get("source") or "supabase"),
                    "title": str(row.get("title") or "Knowledge"),
                    "snippet": self._build_snippet(content, self._tokenize(content)),
                    "score": float(row.get("score") or 0),
                    "retriever": retriever,
                    "tags": list(tags_value),
                    "path": str(row.get("path") or ""),
                    "chunk_index": int(row.get("chunk_index") or 0),
                }
            )
        return normalized

    def _rows_to_chunks(self, rows: list[dict[str, Any]], fallback_source: str) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for index, row in enumerate(rows):
            content = str(row.get("content", "")).strip()
            if not content:
                continue
            tags_value = row.get("tags") or []
            if isinstance(tags_value, str):
                tags_value = [tag.strip() for tag in tags_value.split(",") if tag.strip()]
            chunk_id = str(row.get("id") or f"{fallback_source}-{index}")
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source=str(row.get("source") or fallback_source),
                    title=str(row.get("title") or "Knowledge"),
                    content=content,
                    tags=tuple(tags_value),
                    chunk_index=int(row.get("chunk_index") or index),
                    path=str(row.get("path") or ""),
                )
            )
        return chunks

    def _rank_chunks(self, query: str, chunks: list[KnowledgeChunk], retriever: str) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        query_counter = Counter(query_tokens)
        ranked: list[dict[str, Any]] = []

        for chunk in chunks:
            content_tokens = self._tokenize(chunk.content)
            content_counter = Counter(content_tokens)
            overlap = sum(min(query_counter[token], content_counter[token]) for token in query_counter)
            title_bonus = self._title_bonus(query, chunk.title)
            tag_bonus = sum(2 for tag in chunk.tags if tag in query.lower())
            topic_bonus = self._topic_bonus(query, chunk)
            phrase_bonus = 3 if query.lower() in chunk.content.lower() else 0
            score = overlap + title_bonus + tag_bonus + topic_bonus + phrase_bonus
            if score <= 0:
                continue

            ranked.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "title": chunk.title,
                    "snippet": self._build_snippet(chunk.content, query_tokens),
                    "score": score,
                    "retriever": retriever,
                    "tags": list(chunk.tags),
                    "path": chunk.path,
                    "chunk_index": chunk.chunk_index,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return self._dedupe_results(ranked)

    def _dedupe_results(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            key = (
                str(item.get("source", "")),
                str(item.get("title", "")),
                str(item.get("snippet", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _load_local_chunks(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.corpus_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            title = self._extract_title(text) or path.stem.replace("-", " ").title()
            sections = self._split_into_chunks(text)
            for index, section in enumerate(sections):
                if not section.strip():
                    continue
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"{path.stem}-{index}",
                        source=self._source_label(path),
                        title=title if index == 0 else f"{title} - Part {index + 1}",
                        content=section.strip(),
                        tags=tuple(self._extract_tags(section)),
                        chunk_index=index,
                        path=str(path),
                    )
                )
        return chunks

    def _source_label(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.corpus_dir.parent))
        except ValueError:
            return str(path)

    def _resolve_corpus_dir(self, raw_dir: str) -> Path:
        path = Path(raw_dir)
        if not path.is_absolute():
            root = Path(__file__).resolve().parents[3]
            path = root / raw_dir
        return path

    def _extract_title(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

    def _extract_tags(self, text: str) -> list[str]:
        lowered = text.lower()
        tags = []
        for tag in ["mux", "adder", "vivado", "nand", "nor", "xor", "xnor", "cmos", "verilog", "truth table", "technology node"]:
            if tag in lowered:
                tags.append(tag)
        return tags

    def _split_into_chunks(self, text: str, chunk_size: int = 700, overlap: int = 120) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
        if not paragraphs:
            return [text]

        chunks: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= chunk_size:
                buffer = candidate
                continue
            if buffer:
                chunks.append(buffer)
            if len(paragraph) <= chunk_size:
                buffer = paragraph[-overlap:] if overlap and len(paragraph) > overlap else paragraph
            else:
                start = 0
                while start < len(paragraph):
                    end = min(len(paragraph), start + chunk_size)
                    chunks.append(paragraph[start:end])
                    start = max(end - overlap, end)
                buffer = ""
        if buffer:
            chunks.append(buffer)
        return chunks

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1]

    def _title_bonus(self, query: str, title: str) -> int:
        query_terms = set(self._tokenize(query))
        title_terms = set(self._tokenize(title))
        return len(query_terms & title_terms) * 2

    def _topic_bonus(self, query: str, chunk: KnowledgeChunk) -> int:
        lowered_query = query.lower()
        lowered_content = chunk.content.lower()
        lowered_title = chunk.title.lower()
        bonus = 0
        if "mux" in lowered_query and ("mux" in lowered_content or "mux" in lowered_title or "mux" in chunk.tags):
            bonus += 4
        if "adder" in lowered_query and ("adder" in lowered_content or "adder" in lowered_title or "adder" in chunk.tags):
            bonus += 4
        if "vivado" in lowered_query and ("vivado" in lowered_content or "vivado" in lowered_title):
            bonus += 4
        if "technology" in lowered_query and "technology node" in lowered_content:
            bonus += 3
        return bonus

    def _build_snippet(self, content: str, query_tokens: list[str], window: int = 260) -> str:
        lower = content.lower()
        for token in query_tokens:
            index = lower.find(token)
            if index != -1:
                start = max(0, index - window // 2)
                end = min(len(content), index + window // 2)
                return content[start:end].strip().replace("\n", " ")
        return content[:window].strip().replace("\n", " ")

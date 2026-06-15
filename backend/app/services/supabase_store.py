from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from app.core.settings import settings
from app.schemas.design import DesignContract

try:
    from supabase import create_client
except Exception:  # pragma: no cover - optional dependency import guard
    create_client = None


@dataclass(frozen=True)
class StoreResult:
    status: str
    reason: str = ""
    table: str = ""
    row_id: str = ""
    email: str = ""


class CircuitRepository:
    def __init__(self) -> None:
        self.table = settings.supabase_circuit_table

    def _client(self) -> Any | None:
        if not settings.supabase_url or not settings.supabase_key or create_client is None:
            return None
        return create_client(settings.supabase_url, settings.supabase_key)

    def save_contract(self, contract: DesignContract, prompt: str = "", email: str | None = None) -> dict[str, Any]:
        client = self._client()
        if client is None:
            return StoreResult(status="skipped", reason="Supabase is not configured", table=self.table, email=email or "").__dict__

        attempts = [
            (self.table, self._contract_to_rich_row(contract, prompt, email)),
            (settings.supabase_knowledge_table, self._contract_to_knowledge_row(contract, prompt)),
        ]
        last_error = ""
        for table_name, payload in attempts:
            try:
                response = client.table(table_name).insert(payload).execute()
                data = getattr(response, "data", None) or []
                row_id = str((data[0].get("id") if data else payload.get("record_id") or payload.get("chunk_id")) or "")
                return StoreResult(
                    status="completed",
                    reason="stored in Supabase",
                    table=table_name,
                    row_id=row_id,
                    email=email or "",
                ).__dict__
            except Exception as exc:
                last_error = str(exc)
                continue
        return StoreResult(status="failed", reason=last_error, table=self.table, email=email or "").__dict__

    def search_saved_circuits(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        client = self._client()
        if client is None:
            return []

        rows: list[dict[str, Any]] = []
        for table_name in (self.table, settings.supabase_knowledge_table):
            try:
                response = client.table(table_name).select("*").limit(300).execute()
                rows.extend(getattr(response, "data", None) or [])
            except Exception:
                continue

        query_lower = query.lower()
        ranked: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            text_blob = self._row_text(row)
            if not text_blob.strip():
                continue
            score = self._score(query_lower, text_blob.lower(), row)
            if score <= 0:
                continue
            ranked.append(
                {
                    "chunk_id": str(row.get("id") or row.get("record_id") or f"circuit-{index}"),
                    "source": str(row.get("source") or "supabase-circuits"),
                    "title": str(row.get("title") or row.get("design_name") or "Generated Circuit"),
                    "snippet": self._build_snippet(text_blob, query),
                    "score": score,
                    "retriever": "supabase-circuit-table",
                    "tags": self._row_tags(row),
                    "path": str(row.get("path") or ""),
                    "chunk_index": int(row.get("chunk_index") or 0),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]

    def _contract_to_rich_row(self, contract: DesignContract, prompt: str, email: str | None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "record_id": f"{contract.design_name}:{contract.modeling_style}:{now}",
            "email": email,
            "title": contract.design_name or "generated-circuit",
            "design_name": contract.design_name,
            "design_type": contract.design_type,
            "modeling_style": contract.modeling_style,
            "implementation_profile": contract.implementation_profile,
            "abstraction": contract.abstraction,
            "gate_count": contract.gate_count,
            "technology_node": contract.technology_node,
            "prompt": prompt,
            "inputs": contract.inputs,
            "outputs": contract.outputs,
            "truth_table": [row.model_dump() for row in contract.truth_table],
            "boolean_equation": contract.boolean_equation,
            "verilog": contract.verilog,
            "testbench": contract.testbench,
            "documentation": contract.documentation,
            "fpga_implementation": contract.fpga_implementation,
            "vivado_status": contract.vivado_status,
            "vivado_results": contract.vivado_results.model_dump(),
            "architecture": contract.architecture,
            "retrieved_context_summary": contract.retrieved_context_summary,
            "knowledge_contexts": contract.knowledge_contexts,
            "storage_status": contract.storage_status,
            "created_at": now,
        }

    def _contract_to_knowledge_row(self, contract: DesignContract, prompt: str) -> dict[str, Any]:
        payload = {
            "prompt": prompt,
            "design_name": contract.design_name,
            "design_type": contract.design_type,
            "modeling_style": contract.modeling_style,
            "implementation_profile": contract.implementation_profile,
            "abstraction": contract.abstraction,
            "gate_count": contract.gate_count,
            "technology_node": contract.technology_node,
            "inputs": contract.inputs,
            "outputs": contract.outputs,
            "truth_table": [row.model_dump() for row in contract.truth_table],
            "boolean_equation": contract.boolean_equation,
            "verilog": contract.verilog,
            "testbench": contract.testbench,
            "documentation": contract.documentation,
            "fpga_implementation": contract.fpga_implementation,
            "vivado_status": contract.vivado_status,
            "architecture": contract.architecture,
            "retrieved_context_summary": contract.retrieved_context_summary,
        }
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return {
            "source": "generated-circuit",
            "title": contract.design_name or "generated-circuit",
            "content": content,
            "tags": [
                tag
                for tag in (
                    contract.design_type,
                    contract.modeling_style,
                    contract.implementation_profile,
                    contract.abstraction,
                    contract.technology_node,
                )
                if tag
            ],
            "chunk_index": 0,
            "path": contract.design_name,
        }

    def _row_text(self, row: dict[str, Any]) -> str:
        parts = [
            row.get("title"),
            row.get("design_name"),
            row.get("prompt"),
            row.get("documentation"),
            row.get("boolean_equation"),
            row.get("verilog"),
            row.get("testbench"),
            row.get("retrieved_context_summary"),
        ]
        return "\n".join(str(part or "") for part in parts)

    def _row_tags(self, row: dict[str, Any]) -> list[str]:
        tags = []
        for key in ("design_type", "modeling_style", "implementation_profile", "abstraction", "technology_node"):
            value = row.get(key)
            if value:
                tags.append(str(value))
        return tags

    def _score(self, query_lower: str, content_lower: str, row: dict[str, Any]) -> int:
        score = 0
        for token in self._tokenize(query_lower):
            score += content_lower.count(token)
        title = str(row.get("title") or row.get("design_name") or "").lower()
        score += len(set(self._tokenize(query_lower)) & set(self._tokenize(title))) * 2
        if str(row.get("modeling_style") or "").lower() in query_lower:
            score += 2
        if str(row.get("design_name") or "").lower() in query_lower:
            score += 3
        return score

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in text.split() if len(token) > 1]

    def _build_snippet(self, text: str, query: str, window: int = 260) -> str:
        lower = text.lower()
        for token in self._tokenize(query.lower()):
            index = lower.find(token)
            if index != -1:
                start = max(0, index - window // 2)
                end = min(len(text), index + window // 2)
                return text[start:end].strip().replace("\n", " ")
        return text[:window].strip().replace("\n", " ")

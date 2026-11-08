"""Example: Programmatic Python SDK Usage for RecallX.

Demonstrates initializing the database, creating memories across categories,
searching with BM25 full-text search, multi-signal ranking, and compiling
structured project context.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from recallx.core.memory import MemoryEngine
from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import ProjectRepository


def main() -> None:
    # Use a temporary directory for this demonstration
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "demo_recallx.db"
        print(f"[*] Initializing RecallX database at: {db_path}")

        # 1. Initialize DatabaseManager & MemoryEngine
        db = DatabaseManager(db_path)
        db.initialize()
        engine = MemoryEngine(db)

        # 2. Register a project namespace
        proj_repo = ProjectRepository(db)
        proj_repo.create(
            project_id="ecommerce-api",
            name="E-Commerce Payment Service",
            description="Stripe checkout and webhook processing backend in FastAPI",
            path="/opt/apps/ecommerce-api",
        )
        print("[+] Created project namespace 'ecommerce-api'")

        # 3. Store memories across archetypes
        print("\n[*] Storing sample architectural and technical memories...")

        # Technical Decision
        mem1 = engine.remember(
            content="Using PostgreSQL 15 with SQLAlchemy 2.0 async engine. "
            "PostgreSQL chosen over SQLite for concurrent write locks during webhook ingestion.",
            project_id="ecommerce-api",
            memory_type="decision",
            tags=["database", "postgres", "architecture"],
            importance=0.9,
            source="sdk-demo",
        )
        print(f"  [+] Saved Decision: [{mem1['id']}]")

        # Bug Solution
        mem2 = engine.remember(
            content="Fixed Stripe webhook signature mismatch 400 error. "
            "Root cause: FastAPI request.body() was being read as parsed JSON instead of raw bytes. "
            "Fix: Access await request.body() as bytes before passing to stripe.Webhook.construct_event.",
            project_id="ecommerce-api",
            memory_type="bug_solution",
            tags=["stripe", "webhook", "bugfix"],
            importance=0.85,
            source="sdk-demo",
        )
        print(f"  [+] Saved Bug Solution: [{mem2['id']}]")

        # Developer Preference
        mem3 = engine.remember(
            content="Always use absolute imports from src. Format with Ruff. "
            "Use Pydantic v2 BaseModels for all schema validation and serialization.",
            project_id="ecommerce-api",
            memory_type="preference",
            tags=["style", "standards", "python"],
            importance=0.7,
            source="sdk-demo",
        )
        print(f"  [+] Saved Preference: [{mem3['id']}]")

        # 4. Search with full-text search and relevance ranking
        query = "stripe webhook signature error"
        print(f"\n[*] Searching for memories matching: '{query}'")
        results = engine.recall(query, project_id="ecommerce-api", limit=5)
        for r in results:
            print(f"  [{r.get('relevance', 0.0):.2f}] ID: {r['id']} | Type: {r['memory_type']}")
            print(f"        Content: {r['content'][:90]}...")

        # 5. Compile structured project context
        print("\n[*] Compiling full project context for agent prompt injection:")
        context = engine.get_project_context(project_id="ecommerce-api")
        for mem_type, items in context.get("memories_by_type", {}).items():
            print(f"\n  Category: {mem_type.upper()} ({len(items)} items)")
            for item in items:
                print(f"    - {item['content'][:80]}... (tags: {item['tags']})")

        # 6. Save a session summary
        summary = engine.save_session_summary(
            project_id="ecommerce-api",
            summary="Implemented idempotent Stripe webhook endpoint with signature verification.",
            tasks_completed=[
                "Raw byte payload extraction",
                "Signature verification handler",
                "Event deduplication key storage",
            ],
            tasks_pending=["Refund event processing", "Dead letter queue alerting"],
            issues=["Stripe CLI webhook forwarding has 200ms latency on Windows"],
        )
        print(f"\n[+] Saved Session Summary: [{summary['id']}]")

        # 7. Clean shutdown
        db.close()
        print("\n[✓] Demo completed successfully.")


if __name__ == "__main__":
    main()


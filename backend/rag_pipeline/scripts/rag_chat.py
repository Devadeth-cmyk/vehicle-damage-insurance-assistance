"""Interactive CLI: pick an insurer, ask questions, get Groq-written answers."""

try:
    from . import rag_config as cfg
    from .rag_pipeline import answer_question
    from .search_knowledge_base import get_companies, KnowledgeBaseNotReady
except ImportError:
    import rag_config as cfg
    from rag_pipeline import answer_question
    from search_knowledge_base import get_companies, KnowledgeBaseNotReady

EXIT_WORDS = {"exit", "quit", "q"}


def select_company(companies):
    print("\n" + "=" * 80)
    print("AVAILABLE INSURANCE COMPANIES")
    print("=" * 80)
    for i, name in enumerate(companies, 1):
        print(f"{i}. {name}")
    print("0. All companies")
    print("\nType 'exit' to quit.")

    while True:
        choice = input("\nSelect insurance company: ").strip().lower()
        if choice in EXIT_WORDS:
            return False, None
        if choice == "0":
            return True, None
        if choice.isdigit() and 1 <= int(choice) <= len(companies):
            return True, companies[int(choice) - 1]
        print(f"Please enter a number between 0 and {len(companies)}.")


def main():
    print("=" * 80)
    print("VEHICLE INSURANCE RAG ASSISTANT (Groq)")
    print("=" * 80)

    if not cfg.get_groq_api_key():
        print("\nNote: GROQ_API_KEY is not set - answers will be raw policy excerpts.")

    try:
        companies = get_companies()
    except KnowledgeBaseNotReady as exc:
        print(f"\nERROR: {exc}")
        return
    if not companies:
        print("\nERROR: No insurance companies found in the index.")
        return

    ok, company = select_company(companies)
    if not ok:
        return
    history = []

    print("\nCommands: 'company' = change insurer, 'clear' = reset conversation, 'exit' = quit")

    while True:
        label = company or "All companies"
        question = input(f"\nQuestion ({label}): ").strip()
        low = question.lower()

        if low in EXIT_WORDS:
            break
        if low == "company":
            ok, company = select_company(companies)
            if not ok:
                break
            history = []
            continue
        if low == "clear":
            history = []
            print("Conversation cleared.")
            continue
        if not question:
            continue

        print("\nSearching and generating answer...")
        try:
            result = answer_question(question, company=company, history=history)
        except Exception as exc:  # keep the CLI alive
            print(f"\nERROR: {exc}")
            continue

        print("\n" + "=" * 80)
        print("ANSWER")
        print("=" * 80)
        print(result["answer"])

        if result["sources"]:
            print("\n" + "-" * 80)
            print("SOURCES")
            print("-" * 80)
            for s in result["sources"]:
                print(
                    f"- {s['company']} | {s['document']} | "
                    f"pp.{s['page_start']}-{s['page_end']} | sim {s['similarity']:.3f}"
                )
        if result["mode"] == "retrieval_only":
            print(f"\n(LLM unavailable: {result.get('llm_error', 'unknown')})")

        if result["mode"] == "llm":
            history += [
                {"role": "user", "content": question},
                {"role": "assistant", "content": result["answer"]},
            ]
            history = history[-cfg.MAX_HISTORY_TURNS * 2 :]

    print("\nGoodbye.")


if __name__ == "__main__":
    main()

import os
from dotenv import load_dotenv

load_dotenv()

for name in ["TAVILY_API_KEY", "GROQ_API_KEY"]:
    value = os.getenv(name)
    print(name, "set, length", len(value) if value else "MISSING")


def attempt(label, function):
    print("\n" + label)
    try:
        print("  OK:", function())
    except Exception as error:
        print("  FAILED:", type(error).__name__, "-", str(error)[:300])


def tavily():
    from backend.tools.web_search import search_web
    return str(len(search_web("solid-state batteries"))) + " results"


def groq():
    from backend.services.llm import generate_response
    return generate_response("Say hello in three words.")[:60]


def agent():
    from backend.agents.research_agent import ResearchAgent
    return str(len(ResearchAgent().run("solid-state batteries")["research"])) + " characters"


attempt("1) Tavily search", tavily)
attempt("2) Groq model", groq)
attempt("3) Research agent", agent)

from src.langgraphagenticai.agents.news_agents import (
    CategorizerAgent,
    FactCheckerAgent,
    ResearchAgent,
    ReviewerAgent,
    SaveReportNode,
    SupervisorAgent,
    WriterAgent,
)


class AINewsNode:
    """
    Backward-compatible facade for the refactored AI News agents.

    The AI News workflow is now implemented as dedicated agents and wired in
    graph_builder.py. This class is kept so older imports do not break.
    """

    SupervisorAgent = SupervisorAgent
    ResearchAgent = ResearchAgent
    FactCheckerAgent = FactCheckerAgent
    CategorizerAgent = CategorizerAgent
    WriterAgent = WriterAgent
    ReviewerAgent = ReviewerAgent
    SaveReportNode = SaveReportNode

from typing_extensions import TypedDict,List
from langgraph.graph.message import add_messages
from typing import Annotated, Any, Dict


class State(TypedDict):
    """
    Represent the structure of the state used in graph
    """
    messages: Annotated[List,add_messages]


class NewsState(TypedDict, total=False):
    """
    Represents the state used by the AI News multi-agent workflow.
    """
    messages: Annotated[List, add_messages]
    frequency: str
    raw_articles: List[Dict[str, Any]]
    skipped_articles: List[Dict[str, Any]]
    verified_articles: List[Dict[str, Any]]
    categorized_articles: Dict[str, List[Dict[str, Any]]]
    markdown_report: str
    review_status: str
    reviewer_feedback: str
    revision_count: int
    filename: str
    workflow_status: str
    errors: List[str]
    no_new_articles: bool
    memory_skipped_count: int
    memory_stored_count: int

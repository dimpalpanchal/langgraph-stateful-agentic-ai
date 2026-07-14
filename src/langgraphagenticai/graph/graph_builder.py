from langgraph.graph import StateGraph
from src.langgraphagenticai.state.state import NewsState, State
from langgraph.graph import START,END
from src.langgraphagenticai.nodes.basic_chatbot_node import BasicChatbotNode
from src.langgraphagenticai.tools.search_tool import get_tools,create_tool_node
from langgraph.prebuilt import tools_condition
from src.langgraphagenticai.nodes.chatbot_with_Tool_node import ChatbotWithToolNode
from src.langgraphagenticai.agents.news_agents import (
    CategorizerAgent,
    FactCheckerAgent,
    ResearchAgent,
    ReviewerAgent,
    SaveReportNode,
    SupervisorAgent,
    WriterAgent,
    route_after_review,
)
from src.langgraphagenticai.utils.logging_utils import get_ai_news_logger


logger = get_ai_news_logger()


class GraphBuilder:
    def __init__(self,model):
        self.llm=model
        self.graph_builder=None
        logger.info("[GraphBuilder] Initialized")

    def _with_node_logging(self, node_name, node_callable, reaches_end=False):
        def logged_node(state):
            logger.info("[GraphBuilder] Current Node: %s", node_name)
            result = node_callable(state)
            if reaches_end:
                logger.info("[GraphBuilder] END reached")
            return result

        return logged_node

    def basic_chatbot_build_graph(self):
        """
        Builds a basic chatbot graph using LangGraph.
        This method initializes a chatbot node using the `BasicChatbotNode` class 
        and integrates it into the graph. The chatbot node is set as both the 
        entry and exit point of the graph.
        """

        self.graph_builder=StateGraph(State)
        logger.info("[GraphBuilder] Graph Created: Basic Chatbot")
        self.basic_chatbot_node=BasicChatbotNode(self.llm)

        self.graph_builder.add_node(
            "chatbot",
            self._with_node_logging("chatbot", self.basic_chatbot_node.process, reaches_end=True),
        )
        logger.info("[GraphBuilder] Node added: chatbot")
        self.graph_builder.add_edge(START,"chatbot")
        logger.info("[GraphBuilder] Edge added: START -> chatbot")
        self.graph_builder.add_edge("chatbot",END)
        logger.info("[GraphBuilder] Edge added: chatbot -> END")

    def chatbot_with_tools_build_graph(self):
        """
        Builds an advanced chatbot graph with tool integration.
        This method creates a chatbot graph that includes both a chatbot node 
        and a tool node. It defines tools, initializes the chatbot with tool 
        capabilities, and sets up conditional and direct edges between nodes. 
        The chatbot node is set as the entry point.
        """
        self.graph_builder=StateGraph(State)
        logger.info("[GraphBuilder] Graph Created: Chatbot With Web")

        ## Define the tool and tool node
        tools=get_tools()
        tool_node=create_tool_node(tools)
        logger.info("[GraphBuilder] Tool node created with %s tools", len(tools))

        ## Define the LLM
        llm=self.llm

        ## Define the chatbot node

        obj_chatbot_with_node=ChatbotWithToolNode(llm)
        chatbot_node=obj_chatbot_with_node.create_chatbot(tools)
        ## Add nodes
        self.graph_builder.add_node("chatbot",self._with_node_logging("chatbot", chatbot_node))
        logger.info("[GraphBuilder] Node added: chatbot")
        self.graph_builder.add_node("tools",self._with_node_logging("tools", tool_node))
        logger.info("[GraphBuilder] Node added: tools")
        # Define conditional and direct edges
        self.graph_builder.add_edge(START,"chatbot")
        logger.info("[GraphBuilder] Edge added: START -> chatbot")
        self.graph_builder.add_conditional_edges("chatbot",tools_condition)
        logger.info("[GraphBuilder] Conditional routing configured: chatbot -> tools or END")
        self.graph_builder.add_edge("tools","chatbot")
        logger.info("[GraphBuilder] Edge added: tools -> chatbot")


    def ai_news_builder_graph(self):

        self.graph_builder=StateGraph(NewsState)
        logger.info("[GraphBuilder] Graph Created: AI News Multi-Agent")

        supervisor_agent=SupervisorAgent()
        research_agent=ResearchAgent()
        fact_checker_agent=FactCheckerAgent()
        categorizer_agent=CategorizerAgent()
        writer_agent=WriterAgent(self.llm)
        reviewer_agent=ReviewerAgent()
        save_report_node=SaveReportNode()

        ## added the multi-agent nodes

        self.graph_builder.add_node("supervisor_agent",self._with_node_logging("supervisor_agent", supervisor_agent.plan))
        logger.info("[GraphBuilder] Node added: supervisor_agent")
        self.graph_builder.add_node("research_agent",self._with_node_logging("research_agent", research_agent.research))
        logger.info("[GraphBuilder] Node added: research_agent")
        self.graph_builder.add_node("fact_checker_agent",self._with_node_logging("fact_checker_agent", fact_checker_agent.verify))
        logger.info("[GraphBuilder] Node added: fact_checker_agent")
        self.graph_builder.add_node("categorizer_agent",self._with_node_logging("categorizer_agent", categorizer_agent.categorize))
        logger.info("[GraphBuilder] Node added: categorizer_agent")
        self.graph_builder.add_node("writer_agent",self._with_node_logging("writer_agent", writer_agent.write))
        logger.info("[GraphBuilder] Node added: writer_agent")
        self.graph_builder.add_node("reviewer_agent",self._with_node_logging("reviewer_agent", reviewer_agent.review))
        logger.info("[GraphBuilder] Node added: reviewer_agent")
        self.graph_builder.add_node(
            "save_report",
            self._with_node_logging("save_report", save_report_node.save, reaches_end=True),
        )
        logger.info("[GraphBuilder] Node added: save_report")

        #added the edges

        self.graph_builder.add_edge(START,"supervisor_agent")
        logger.info("[GraphBuilder] Edge added: START -> supervisor_agent")
        self.graph_builder.add_edge("supervisor_agent","research_agent")
        logger.info("[GraphBuilder] Edge added: supervisor_agent -> research_agent")
        self.graph_builder.add_edge("research_agent","fact_checker_agent")
        logger.info("[GraphBuilder] Edge added: research_agent -> fact_checker_agent")
        self.graph_builder.add_edge("fact_checker_agent","categorizer_agent")
        logger.info("[GraphBuilder] Edge added: fact_checker_agent -> categorizer_agent")
        self.graph_builder.add_edge("categorizer_agent","writer_agent")
        logger.info("[GraphBuilder] Edge added: categorizer_agent -> writer_agent")
        self.graph_builder.add_edge("writer_agent","reviewer_agent")
        logger.info("[GraphBuilder] Edge added: writer_agent -> reviewer_agent")
        self.graph_builder.add_conditional_edges(
            "reviewer_agent",
            route_after_review,
            {
                "writer_agent": "writer_agent",
                "save_report": "save_report",
            },
        )
        logger.info("[GraphBuilder] Conditional routing configured: reviewer_agent -> writer_agent or save_report")
        self.graph_builder.add_edge("save_report", END)
        logger.info("[GraphBuilder] Edge added: save_report -> END")



    def setup_graph(self, usecase: str):
        """
        Sets up the graph for the selected use case.
        """
        if usecase == "Basic Chatbot":
            self.basic_chatbot_build_graph()
        if usecase == "Chatbot With Web":
            self.chatbot_with_tools_build_graph()
        if usecase == "AI News":
            self.ai_news_builder_graph()

        logger.info("[GraphBuilder] Compiling graph for usecase: %s", usecase)
        return self.graph_builder.compile()

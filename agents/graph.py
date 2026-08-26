# StateGraph: build AI workflow (graph) and END: a marker that tells graph to stop
from langgraph.graph import StateGraph, END

# ToolNode: a ready-made node that auto runs tools
from langgraph.prebuilt import ToolNode

from langgraph_checkpoint_aws import DynamoDBSaver
from .state import AgentState
from .nodes import decompose_query, agent_node, report_generate, should_continue
from tools import web_search, arxiv_search, rag_query

TOOLS = [web_search, arxiv_search, rag_query]

def build_graph():
    """
    Build LangGraph state graph.

    Flow:
    decompose → agent → tools → agent (loop if needed)
                  ↓
                report → END
    """

    # Create a checkpointer backed by DynamoDB, so conversation state
    # survives process restarts (unlike MemorySaver, which lives only in RAM).
    checkpointer = DynamoDBSaver(
        table_name="research-agent-checkpoints",
        region_name="us-east-1",
    )

    # Create the graph, AgentState is the shared data bag
    workflow = StateGraph(AgentState)

    # register node
    workflow.add_node("decompose",decompose_query)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.add_node("report", report_generate)

    #define execution flow
    workflow.set_entry_point("decompose")
    workflow.add_edge("decompose","agent")

    # After agent, decide the next step based on should_continue()
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools":"tools",
            "report":"report",
            END:END
        }
    )

    # After tools finish, loop back to agent to think again
    workflow.add_edge("tools","agent")

    # After report is done, stop the graph
    workflow.add_edge("report",END)

    # Compile everything into a runnable graph with memory enabled
    return workflow.compile(checkpointer=checkpointer)
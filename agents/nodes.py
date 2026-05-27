import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .state import AgentState
from config.prompts import SYSTEM_PROMPT, DECOMPOSE_PROMPT, REPORT_PROMPT
from config.settings import LLM_MODEL, MAX_STEPS
from tools import web_search, arxiv_search, rag_query

# LLM instance( shared between nodes)
llm = ChatOpenAI(model=LLM_MODEL, temperature=0) # temperature controls randomnes and creativity

def decompose_query(state:AgentState) -> dict:
    """
    Node 1: Query Decomposition
    Break down the user’s question into 3‑5 sub‑queries.

    User Query
        ↓
    LLM Decomposes Sub‑Queries
        ↓
    Parse JSON
        ↓
    Save to AgentState
        ↓
    Return Updated State
    """

    query = state["messages"][-1].content # get the newest user question
    """
    state is something like
     {"message":[msg1,msg2,msg3]}
    """

    # invoke LLM
    response = llm.invoke([
        SystemMessage(content=DECOMPOSE_PROMPT), # define AI
        HumanMessage(content=f"Research question:{query}") # user question
    ])

    try:
        data = json.loads(response.content) # JSON string to Python Dict
        sub_queries = data.get("sub_queries", [query]) # if output {}, return user question

    except json.JSONDecodeError:
        # LLMs sometimes fail to decompose/follow output formatting; fall back to the original query
        sub_queries = [query]

    # print log
    print(f"[decompose] Sub-queries: {sub_queries}")

    # return state data
    return{
        "original_query": query,
        "sub_queries": sub_queries,
        "step_count": 0,
        "current_step": "Query decomposed, starting research...",
        "loaded_papers": [],
        "retrieved_docs": [],
        "final_report": ""
    }

def agent_node(state:AgentState) -> dict:
    """
    Node 2: Agent Decision Node (Core of ReAct)
    The LLM reviews current messages to decide which tool to call, or to generate a final report if it gets enough info.

    Read Current State
         ↓
    give LLM System Rules
         ↓
    Inform LLM of Available Tools
         ↓
    Send Historical Messages to LLM
         ↓
    LLM Decides:
     - Call tools?
     - Or answer directly?
         ↓
    Return New Messages and Updated State
    """

    # bind tools: inform the LLM of available tools
    llm_with_tools = llm.bind_tools([web_search, arxiv_search, rag_query])

    step = state["step_count"] + 1

    # If it is the first step, add sub‑queries into the system message
    if step == 1:
        # Get all sub-queries
        sub_queries = state.get("sub_queries", [])

        # Convert list to bullet-point text
        sub_q_text = "\n".join([f"- {q}" for q in sub_queries])

        # Add sub-queries into system prompt
        system_content = (
                SYSTEM_PROMPT
                + "\n\nSub-queries to research:\n"
                + sub_q_text
        )

    else:
        system_content = SYSTEM_PROMPT

    messages = [SystemMessage(content=system_content)] + state["messages"] # combine system prompt and history message
    response = llm_with_tools.invoke(messages) # send it to LLM

    return {
        "messages": [response],
        "step_count": step,
        "current_step": f"Step {step}: Agent reasoning..."
    }

def report_generate(state: AgentState) -> dict:
    """
    Node 3: Report Generation
    Collect all retrieved information and generate a research report.

    Query → Decompose → Retrieve → Agent reasoning → Tools → Report
                                                  ↓
                                         report_generate()

    """

    # Extract tool outputs from message history
    tool_results = []
    for msg in state["messages"]:
        # Check if message has content and it is a string
        if hasattr(msg, "content") and isinstance(msg.content, str):

            # Filter out short/noisy messages
            if len(msg.content) > 100:
                tool_results.append(msg.content)

    # Combine recent results into a single context string
    context = "\n\n===\n\n".join(tool_results[-10:])  # last 10 results

    # Call LLM to generate final report
    report_response = llm.invoke([
        SystemMessage(content=REPORT_PROMPT),

        HumanMessage(content=f"""
                            Original question: {state['original_query']}

                            Research context:
                            {context}

                            Generate a comprehensive structured report based on the above information.
                            """)
    ])

    # Return final report and update status
    return {
        "final_report": report_response.content,
        "current_step": "Report generated!"
    }

def should_continue(state: AgentState) -> str:
    """
    Conditional edge:
    Decide the next step in the graph workflow.

    Return value must match keys defined in conditional_edges mapping.
    """

    # Get message history
    messages = state["messages"]
    last_message = messages[-1]

    # Get current step count (default = 0)
    step_count = state.get("step_count", 0)

    # Force stop condition: max steps reached
    if step_count >= MAX_STEPS:
        print(f"[should_continue] Max steps ({MAX_STEPS}) reached, forcing report")
        return "report"

    # If LLM requested tool calls → go to tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise → go to report generation
    return "report"

import streamlit as st
from langchain_core.messages import HumanMessage
from agents import build_graph
from tools.export import export_txt, export_docx, export_pdf
from datetime import datetime

"""

"""

st.set_page_config(
    page_title = "AI Research Agent",
    layout = "wide"
)

st.title("AI Research Agent") # the heading at the top of the page

# --------------Sidebar------------------

with st.sidebar:
    st.header('configuration')

    thread_id = st.text_input(
        "Session ID",
        value="session-1",
        help="Same ID = Shared memory across conversation"
        # Text box for the session ID; same ID lets the agent remember prior turns
    )

    if st.button("clear session"):
        # If the user clicks the button, wipe the chat history
        st.session_state.message = [] # reset message list to empty
        st.success("Session cleared") # show a green confirmation banner

    st.divider() # draw a separator line

    st.header('instruction:')
    st.markdown("""
    1. Enter a research question
    2. Agent decomposes it into sub-queries for high efficiency
    3. Search arXiv papers or relevant website
    4. Downloads papers
    5. Generates report
    6. export as PDF, WORD or TXT(optional)
    """)

# ------------Session state init-----------------

# create an empty list to store chat on the first load
if "messages" not in st.session_state:
    st.session_state.messages = []

#----------------- Render chat history--------------------

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # render each stored message in a chat bubble
        st.markdown(message["content"])

# ------------Handle new user input-------------------

if prompt := st.chat_input("Enter your research question:"):
    # show the input box at the bottom
    # thd block below only runs when user submits a message

    # display user message and save the new message
    st.session_state.messages.append({"role":"user","content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt) # render user-style bubble

    # ---------- Agent execution ---------------
    with st.chat_message("assistant"):

        # live update agent's status
        status_placeholder = st.empty()
        report_placeholder = st.empty()

        try:
            graph = build_graph()

            config = {"configurable":{"thread_id":thread_id}}

            with st.spinner("🔍 Researching..."):
                # show a loading spinner while agent runs

                # streaming: yield a chunk as each node finished
                for chunk in graph.stream(
                    {"messages":[HumanMessage(content=prompt)]},
                    config = config,
                    stream_mode = "updates" # Yield output after each node complete
                ):

                    # iterate over each node's output when it finishes
                    # if output include current_step, the status line will be updated. user will see sm like: Searching arXiv...
                    for node_name, node_output in chunk.items():
                        current_step = node_output.get("current_step","")
                        if current_step:
                            status_placeholder.info(
                                f"**{node_name}**:{current_step}"
                            )
                            # show live time progress

            # ----------------Retrieve final result -------------------

            state = graph.get_state(config)
            final_report = state.values.get("final_report", "")

            status_placeholder.empty()  # Remove the last status message

            if final_report:
                report_placeholder.markdown(final_report) # render report

                # save the report to chat history
                st.session_state.messages.append({
                    "role":"assistant",
                    "content":final_report
                })

                # save report into session_state for exporting
                st.session_state.last_report = final_report
                st.session_state.last_query = prompt

            else:
                report_placeholder.warning(
                    "No report generated. Try a more specfic questiion."
                )

        except Exception as e:
            st.error(f"Error:{str(e)}") # show a concise red error banner
            st.exception(e)
            # print the full traceback


# ── Export area (only shown when the report is generated) ──────────────────────────────

if st.session_state.get("last_report"):
    st.divider()
    st.subheader("Export Report")

    report   = st.session_state.last_report
    query    = st.session_state.get("last_query", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.download_button(
            label="Download TXT",
            data=export_txt(report, query),
            file_name=f"report_{timestamp}.txt",
            mime="text/plain",
        )
    with col2:
        st.download_button(
            label="Download DOCX",
            data=export_docx(report, query),
            file_name=f"report_{timestamp}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with col3:
        st.download_button(
            label="Download PDF",
            data=export_pdf(report, query),
            file_name=f"report_{timestamp}.pdf",
            mime="application/pdf",
        )
    with col4:
        if st.button("✕ Skip"):
            # so the export area disappears after skip
            st.session_state.pop("last_report", None)
            st.session_state.pop("last_query", None)
            st.rerun()




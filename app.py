# app.py

import streamlit as st
from agent import workflow # Import the workflow definition
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
import uuid
import re # Import the regular expression module

st.set_page_config(page_title="Interactive Travel Agent", layout="wide")
st.title("AI Interactive Travel Agent")

# --- HELPER FUNCTION TO CLEAN THE RESPONSE ---
def clean_response_text(text: str) -> str:
    """
    Cleans the raw output from the LLM by removing unwanted function call tags.
    """
    # This regex pattern finds and removes the <function=...>...</function> tags
    pattern = r"<function=.*?>.*?</function>"
    # re.sub replaces the found pattern with an empty string
    # .strip() removes any leading/trailing whitespace
    return re.sub(pattern, "", text).strip()

# --- SESSION STATE MANAGEMENT ---
if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = MemorySaver()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [AIMessage(content="Hello! How can I help you plan your trip today?")]

# --- COMPILE THE GRAPH ---
@st.cache_resource
def get_app():
    return workflow.compile(
        checkpointer=st.session_state.checkpointer,
        interrupt_before=["interrupt"]
    )
app = get_app()

# --- DISPLAY CHAT HISTORY ---
for msg in st.session_state.messages:
    if msg.type == "human":
        st.chat_message("user").write(msg.content)
    else:
        st.chat_message("assistant").write(msg.content)

# --- HANDLE USER INPUT ---
if prompt := st.chat_input("What is your travel plan?"):
    st.chat_message("user").write(prompt)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    events = app.stream(
        {"messages": [HumanMessage(content=prompt)]}, config, stream_mode="values"
    )

    full_response = None
    for event in events:
        if "messages" in event:
            full_response = event["messages"]
    
    if full_response:
        # Get the final message from the agent
        agent_response_message = full_response[-1]
        
        # **CLEAN THE CONTENT** before displaying and saving
        cleaned_content = clean_response_text(agent_response_message.content)
        
        # Update the message object with the cleaned content
        agent_response_message.content = cleaned_content
        
        # Overwrite the session state with the full, NOW CLEANED history
        st.session_state.messages = full_response
        
        # Display the cleaned message in the UI
        st.chat_message("assistant").write(cleaned_content)
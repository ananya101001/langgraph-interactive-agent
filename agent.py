# agent.py

import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, Sequence
import operator
from functools import partial

# LangChain Imports
from langchain_core.messages import BaseMessage, AIMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch

# LangGraph Imports
from langgraph.graph import StateGraph, END

# --- 1. SETUP: Load Environment Variables and Define the LLM ---
load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# --- 2. DEFINE TOOLS ---
tavily_tool = TavilySearch(max_results=3, name="search_activities")
tavily_tool.description = "Searches for activities and things to do in a given location. Input should be a city name."

@tool
def search_flights(destination: str, budget: int) -> str:
    """Mock tool to search for flights given a destination and a budget."""
    print(f"--- TOOL: Searching flights for {destination} with budget {budget} ---")
    return f"I found two flights to {destination}. A direct flight for ${budget + 100} and one with a layover for ${budget - 50}. Which do you prefer?"

@tool
def search_hotels(destination: str) -> str:
    """Mock tool to search for hotels in a given destination."""
    print(f"--- TOOL: Searching hotels for {destination} ---")
    return f"I found three great hotels in {destination}: 'The Grand Plaza' (luxury), 'City Center Inn' (mid-range), and 'Budget Stay' (economy). What's your preference?"

tools = [tavily_tool, search_flights, search_hotels]

# --- 3. DEFINE AGENT STATE ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- 4. DEFINE THE AGENT ---
def create_agent(llm, tools):
    """Helper function to create a tool-calling agent."""
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful and proactive travel planning assistant. Your mission is to collaboratively create a complete travel itinerary with the user. "
         "\n\n**Your Process is Rigid and You MUST follow it Step-by-Step:**"
         "\n\n1. **Greet and Clarify:** Start by greeting the user. If they have not provided a destination, budget, and number of days, you MUST ask for the missing information. Do not proceed until you have these three pieces of information."
         "\n\n2. **Flights (Mandatory First Step):** Once you have the destination and budget, you MUST use the `search_flights` tool. Present the options to the user. You are NOT allowed to choose for them. Wait for their explicit confirmation (e.g., 'I'll take the direct flight')."
         "\n\n3. **Hotels (Mandatory Second Step):** After the user has chosen a flight, you MUST use the `search_hotels` tool. Present the options to the user. You are NOT allowed to choose for them. Wait for their explicit confirmation (e.g., 'The Grand Plaza sounds good')."
         "\n\n4. **Activities (Mandatory Third Step):** After the user has chosen a hotel, you MUST use the `search_activities` tool. Suggest 1-2 activities based on their interests or the destination. Ask if they would like to add them to the itinerary."
         "\n\n5. **Final Itinerary:** ONLY after the user has explicitly confirmed a flight, a hotel, AND at least one activity, you can generate the final plan. Your final response MUST begin with the exact phrase 'Here is your final itinerary:' to signify completion."
         "\n\n**Crucial Rule:** Do NOT invent or assume user choices. Your job is to present options and wait for a decision at each step."),
        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return executor

# --- 5. DEFINE THE GRAPH NODES ---
def agent_node(state, agent):
    """Node that runs the agent executor."""
    result = agent.invoke(state)
    return {"messages": [AIMessage(content=result["output"])]}

def router(state) -> str:
    """Router to decide the next step."""
    last_message = state["messages"][-1]
    if "Here is your final itinerary:" in last_message.content:
        return "end"
    else:
        return "interrupt"

# --- 6. ASSEMBLE THE GRAPH DEFINITION (DO NOT COMPILE) ---
agent = create_agent(llm, tools)
workflow = StateGraph(AgentState)
workflow.add_node("agent", partial(agent_node, agent=agent))
workflow.add_conditional_edges("agent", router, {"end": END, "interrupt": "interrupt"})
workflow.set_entry_point("agent")
workflow.add_node("interrupt", lambda state: state)
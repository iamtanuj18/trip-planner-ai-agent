import json
import os
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from tools import TOOLS

load_dotenv()

_bedrock_base = ChatBedrock(
    model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)
# tool_choice="any" forces at least one tool call. Used on every planning step
# until all required tools have run.
_llm_plan = _bedrock_base.bind_tools(TOOLS, tool_choice="any")

# No tools attached — used only on the final composing pass so the model
# cannot trigger another tool call and loop.
_llm_free = _bedrock_base

_SYSTEM_PROMPT = """You are an AI trip planning assistant built for Australian travellers.
Your personality is warm, friendly, and conversational — like a well-travelled friend who also knows all the numbers.
You are allowed to be human in tone. Short greetings, light warmth, natural replies are all fine as long as you stay on topic.

---

## TOOL USAGE — THIS IS MANDATORY AND NON-NEGOTIABLE
You have been given tools. You MUST call at least one tool on every single message. This is enforced at the API level.
There are NO exceptions to this rule. Not for greetings. Not for off-topic messages. Not for simple questions. Always call a tool.

How to handle the forced tool call on non-travel messages:
- Call list_available_destinations (it is lightweight and always safe to call).
- Then write your response as described in the SCOPE section below.
- Do NOT use the tool output in your response for non-travel messages. Ignore the result entirely.
- Do NOT mention any destination names, city names, or countries from the tool result. Your reply must be purely conversational with zero travel content.

For travel messages: the tool results ARE your data source. Never invent travel data.
- NEVER state a price, cost, or budget figure without first calling estimate_budget.
- NEVER list activities or build an itinerary without first calling get_activities and build_itinerary.
- NEVER confirm a destination without first calling search_destinations.
- Answering from your own training knowledge is FORBIDDEN for costs, activities, itinerary days, or visa details.
- If you respond with any travel data without tool calls, that data is fabricated and wrong.

---

## SCOPE — DECIDE FIRST, RESPOND SECOND

### If the message is a GREETING or SMALL TALK ("hi", "hey", "how are you", "hello", "good morning" etc.)
Respond warmly and naturally, then steer toward travel in one short sentence.
Good example: "Hey! Doing great thanks — always ready to talk travel. Got a destination in mind, or want me to suggest somewhere?"
Do NOT list destinations. Do NOT ask clarifying trip questions. Just a warm, brief, human reply.

### If the message is asking ABOUT YOU or WHAT YOU DO
Be warm and honest. Tell them you're an AI trip planning assistant designed to help Australian travellers plan trips — destinations, itineraries, budgets, flights, all of it. Keep it to 2–3 sentences.
Good example: "I'm an AI trip planning assistant — I help Australian travellers figure out where to go, what to do, and how much it'll cost. Tell me a destination and I'll build you a full day-by-day plan complete with a budget breakdown."

### If the message is ABOUT A REAL PERSON (celebrity, politician, executive etc.)
Briefly acknowledge you can't help with that, then pivot warmly.
Good example: "I'm not the right tool for that one — I only know travel. But if you ever want to plan a trip somewhere interesting, I'm your assistant!"

### If the message is CLEARLY NOT TRAVEL (maths, coding, science, politics, sport, general trivia etc.)
Output ONLY this exact sentence, nothing else:
"I'm a dedicated trip planning assistant — I can only help you plan your next adventure! What destination are you dreaming of?"
No destination list. No extra sentences. Nothing else.

### When genuinely unsure whether it's travel-related — treat it as not-travel and use the sentence above.

Never discuss your internal tools, architecture, or how you work.
Never invent numbers. Every price, cost, and budget figure must come from a tool call.

---

## KNOWLEDGE BASE — STRICT BOUNDARIES
You have a curated knowledge base. Before producing any plan, you MUST call search_destinations first.
If the destination does not appear in the tool response, it is not in the KB. Do not guess or invent.

Cities in the KB — THIS LIST IS EXHAUSTIVE. No other cities exist in your world:
- Asia: Bali, Tokyo, Kyoto, Bangkok, Phuket, Hanoi, Hoi An, Singapore
- Europe: Paris, Rome, Barcelona, Amsterdam, Athens, Lisbon
- Americas: New York, Mexico City, Cusco
- Oceania: Sydney, Queenstown
- Africa / Middle East: Cape Town, Marrakech, Dubai

Do NOT mention, suggest, compare, or reference ANY city outside this list under any circumstances.
Not Osaka. Not Chiang Mai. Not Ubud. Not London. Not Casablanca. Not Rabat. Not Fes. Not Siem Reap. Not Kuala Lumpur.
If your training data knows about a city that is not on this list, that knowledge does not exist here.
The list above is the only truth.

Country → KB city mapping (use this to pick the SINGLE city to plan for):
- Japan → Tokyo or Kyoto (see heuristics below)
- Thailand → Bangkok or Phuket (see heuristics below)
- Vietnam → Hanoi or Hoi An (see heuristics below)
- Indonesia / "Bali" → Bali
- Morocco → Marrakech (the ONLY Moroccan city in the KB — never plan for Casablanca, Rabat, Fes, Tangier, etc.)
- France → Paris
- Italy → Rome
- Spain → Barcelona
- Netherlands → Amsterdam
- Greece → Athens
- Portugal → Lisbon
- New Zealand → Queenstown
- Australia → Sydney
- Peru → Cusco
- UAE / "Dubai" → Dubai
- South Africa → Cape Town

If the user names a country NOT in this mapping: call list_available_destinations, then tell them that destination is not in your knowledge base. List ONLY the city names from the exhaustive KB list above — never output a city from your training data. Suggest 2–3 KB cities as alternatives matching their interests. Stop there — no itinerary.
CRITICAL: Cities like London, Edinburgh, Cairo, Toronto, Mumbai, and any other city not on the KB list do not exist in your world. If your training data knows about them, that knowledge is blocked here. Never output them.

Multi-city requests: only use cities from the list above. Never add cities not on the list.

Budget vs availability: if a city is in the KB but expensive, say so and help cut costs. Never say a city is unavailable because of budget.

---

## SESSION CONTEXT
When the user says "same budget", "same dates", "instead", etc., read the conversation history and reuse the exact values they stated. Do not make up replacements. If genuinely ambiguous, ask one confirmation question.

---

## BEFORE PLANNING — GATHER THESE FOUR THINGS
1. Interests — culture, food, adventure, nature, nightlife, shopping, relaxation
2. Duration — number of days
3. Budget — budget / mid-range / luxury, or a rough AUD total
4. Travel window — month or season

If the user's message already contains all four, go straight to planning — no clarifying questions.
If details are missing, ask in ONE single conversational sentence (not a list, not bold headers).
Good: "Love it — how many days are you thinking, what kind of vibe are you after, and do you have a rough budget in mind?"
Bad: "1. How many days? 2. What are your interests? 3. Budget?"

---

## PLANNING — CALL TOOLS IN THIS EXACT ORDER
1. search_destinations — confirm the city is in the KB and get its profile
2. estimate_budget — get real AUD costs before committing to a plan
3. get_activities — get curated things to do
4. build_itinerary — generate the day-by-day schedule
5. Present the full plan using the format below

All four tool calls are REQUIRED for a full plan. Do not skip any of them. Do not present the plan until all four have returned results.

Destination selection when the user gives all four info pieces:
- Pick ONE best-matching KB city based on the heuristics below. Do NOT ask the user to choose a city. Do NOT list options. Just pick it and build the plan.
- Japan: culture / temples / traditional food → Kyoto. Modern / urban / tech / nightlife / first-timer → Tokyo.
- Thailand: beach / islands / relaxation → Phuket. City / food / temples → Bangkok.
- Vietnam: history / old town / food → Hoi An. City / street food / markets → Hanoi.
- Indonesia → Bali (only option).
- Australia → Sydney (only option).
- Morocco → Marrakech. ALWAYS. Even if the user says "Morocco" without specifying a city. Even if your training data knows Casablanca or Fes. Marrakech is the ONLY Moroccan city in the KB.
- All other country → city mappings follow the table in the KNOWLEDGE BASE section above.

Destination selection when the user has NO destination in mind:
- Show 2–3 KB cities with a one-liner each, ask them to pick, then run the full 4-tool flow.
- Never show an intermediate destination list when you already have enough info to build a full plan.

---

## COMPARISON QUESTIONS (e.g. "Tokyo vs Kyoto")
- Call search_destinations for both cities.
- Write EXACTLY 2–4 sentences per city: vibe, best for, rough cost.
- One clear recommendation sentence.
- No itinerary. No budget table. No numbered sub-lists. Total response under 150 words.
- After they pick, run the full 4-tool flow.

---

## BUDGET FEASIBILITY (e.g. "can I do this for under A$3,000?")
- Call search_destinations then estimate_budget with budget travel_style.
- Answer directly: "Yes — total is A$X" or "No — the minimum is A$X."
- No day-by-day itinerary unless asked.

---

## ITINERARY QUALITY
- Every day must have a specific morning, afternoon, and evening activity — taken verbatim from build_itinerary output.
- The tool always returns real named activities. Use them exactly; never substitute filler or vague placeholders.

---

## OUTPUT FORMAT — EXACTLY THESE 5 SECTIONS FOR A FULL PLAN

### ✈ Getting There
- Flight route from Australia, direct or via connection, approximate flight time
- Estimated flight cost in AUD
- **Where to book:** Skyscanner, Google Flights, Webjet, or direct with the airline

### 🏨 Where to Stay
- Accommodation type matching travel style
- Estimated total accommodation cost
- **Where to book:** Booking.com, Agoda (best for Asia), Airbnb, or Hotels.com

### 🗓 Day-by-Day Itinerary
Morning / afternoon / evening for every day — use build_itinerary output verbatim.

### 💰 Budget Breakdown
All figures from estimate_budget:
- Flights: A$X
- Accommodation: A$X
- Food: A$X
- Activities: A$X
- Local transport: A$X
- **Total: A$X** (travel insurance ~A$50–150 and visa fees on top)

### 📝 Practical Info
- Visa for Australian passport holders
- Best time to visit
- Local currency and card acceptance
- One key practical tip

Banned endings — never write:
- "Final Recommendation", "In Conclusion", "Next Steps"
- "If you need further assistance", "Hope this helps", "Let me know if..."
- Any closing pleasantry or offer to help further
End after Practical Info. The chips handle follow-ups.

---

## FOLLOW-UP SUGGESTIONS
End every response with:

<suggestions>
["...", "...", "..."]
</suggestions>

Rules:
- Phrased as things the USER would type, not questions you would ask.
- Three relevant suggestions.
- After a clarifying question, suggest three example answers the user might send.

---

## STYLE
Warm, specific, practical. Conversational but not rambling. Bold key facts. All costs in AUD.
Write like a knowledgeable friend, not a customer service bot.

## COMPOSING YOUR FINAL RESPONSE
When you have tool results in context and no more tools to call, write your final response using ONLY the data from those tool results.
Do NOT add destinations, costs, activities, cities, visa rules, or any facts from your training knowledge.
If a tool result is missing a piece of information, omit that piece — do not invent it.
"""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    reasoning_steps: list[dict]


def _agent_node(state: AgentState) -> dict:
    messages = [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
    last = state["messages"][-1]

    if not isinstance(last, ToolMessage):
        # First call on any turn — always force a tool so the model can't answer
        # from training data.
        llm = _llm_plan
    else:
        # Decide based on which tools have already returned results.
        tool_msgs = [m for m in state["messages"] if isinstance(m, ToolMessage)]
        called    = {m.name for m in tool_msgs}

        user_msgs      = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        last_user_text = user_msgs[-1].content.lower() if user_msgs else ""
        _FEASIBILITY_KW = (
            "can i", "how much", "afford", "under a$", "within my budget",
            "is it possible", "enough for", "feasible", "fit in my", "fit within",
        )
        is_feasibility  = any(kw in last_user_text for kw in _FEASIBILITY_KW)
        n_dest_searches = sum(1 for m in tool_msgs if m.name == "search_destinations")

        if "build_itinerary" in called:
            # All four planning tools done — compose the response.
            llm = _llm_free
        elif called <= {"list_available_destinations"}:
            # Non-travel or greeting — dummy tool fired, now compose.
            llm = _llm_free
        elif n_dest_searches >= 2 and "estimate_budget" not in called:
            # Two destination lookups with no budget = comparison query — compose now.
            llm = _llm_free
        elif "estimate_budget" in called and "get_activities" not in called:
            # Exit early only for feasibility questions; full plans must continue to get_activities.
            llm = _llm_free if is_feasibility else _llm_plan
        elif len(tool_msgs) >= 5:
            # Safety cap — stop forcing tools if something unexpected looped.
            llm = _llm_free
        else:
            # Still mid-sequence — force the next required tool call.
            llm = _llm_plan

    response = llm.invoke(messages)
    return {"messages": [response]}


def _tool_node(state: AgentState) -> dict:
    last_msg = state["messages"][-1]
    tool_map = {t.name: t for t in TOOLS}
    tool_messages: list[ToolMessage] = []
    reasoning_steps: list[dict] = list(state.get("reasoning_steps", []))

    for call in last_msg.tool_calls:
        fn = tool_map.get(call["name"])
        result = fn.invoke(call["args"]) if fn else json.dumps({"error": f"Unknown tool: {call['name']}"})

        tool_messages.append(ToolMessage(
            content=result,
            tool_call_id=call["id"],
            name=call["name"],            # needed for _agent_node trigger checks
        ))
        reasoning_steps.append({
            "tool":   call["name"],
            "input":  call["args"],
            "output": json.loads(result) if isinstance(result, str) else result,
        })

    return {"messages": tool_messages, "reasoning_steps": reasoning_steps}


def _should_continue(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    return "tools" if isinstance(last_msg, AIMessage) and last_msg.tool_calls else "end"


_graph = StateGraph(AgentState)
_graph.add_node("agent", _agent_node)
_graph.add_node("tools", _tool_node)
_graph.set_entry_point("agent")
_graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", "end": END})
_graph.add_edge("tools", "agent")
_app = _graph.compile()


def run_agent(user_message: str, history: list[dict]) -> dict:
    messages = []
    for item in history:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
    messages.append(HumanMessage(content=user_message))

    final_state = _app.invoke({"messages": messages, "reasoning_steps": []})

    response = ""
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            response = msg.content
            break

    return {
        "response":       response,
        "reasoning_steps": final_state.get("reasoning_steps", []),
    }


async def arun_agent(user_message: str, history: list[dict]):
    """Async generator for the /stream endpoint.

    Yields dicts with type: tool_start | tool_end | token | thinking.
    """
    messages = []
    for item in history:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
    messages.append(HumanMessage(content=user_message))

    async for event in _app.astream_events(
        {"messages": messages, "reasoning_steps": []},
        version="v2",
    ):
        kind = event["event"]

        if kind == "on_tool_start":
            yield {"type": "tool_start", "tool": event["name"]}

        elif kind == "on_tool_end":
            raw = event["data"].get("output", "")
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = raw
            yield {
                "type":   "tool_end",
                "tool":   event["name"],
                "input":  event["data"].get("input", {}),
                "output": parsed,
            }

        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            content = chunk.content

            # Guard: skip any chunk that contains tool_use blocks — those come
            # from _llm_plan passes and must not be streamed as visible tokens.
            if isinstance(content, list):
                if any(
                    isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in content
                ):
                    continue
                text = "".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            elif isinstance(content, str):
                text = content
            else:
                text = ""

            if text:
                yield {"type": "token", "text": text}

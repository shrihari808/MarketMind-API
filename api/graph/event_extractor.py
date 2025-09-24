# aigptssh/api/graph/event_extractor.py
import asyncio
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import GPT4o_mini as llm

async def extract_events(text: str):
    """
    Extracts structured market events from a given text using an LLM.
    """
    system_prompt = """
You are a Financial Market Event Extraction Assistant.

Your task:
- Analyze financial text inputs (headlines, articles, PRs, regulatory filings, govt notifications, speeches).
- Extract ALL explicit or strongly implied market-moving events.
- Return structured JSON output (one object per event).
- Ensure coverage across corporate, sectoral, macroeconomic, political, and geopolitical events, with special focus on Indian markets (NSE/BSE, RBI, SEBI, ministries, industries, commodities) but include global events impacting India.

---
Event Categories (map each event to exactly one type):

1. Corporate / Company Events
   - Earnings / Results (quarterly/annual, profit warnings, dividends, buybacks)
   - Fundraising (IPO, FPO, QIP, rights issue, debt issuance, bond sale, venture funding)
   - M&A / Corporate Restructuring (acquisitions, mergers, demergers, asset sales, JVs, spin-offs)
   - Partnerships / Deals / Contracts (alliances, vendor contracts, PSU contracts, MoUs)
   - Product / Service Launches (new products, services, features, plants, R&D breakthroughs)
   - Leadership / Board Changes (CEO/CFO exits, key hires, board reshuffles, resignations)
   - Operational Events (plant openings/closures, capacity expansions, strikes, labor unrest, supply chain disruptions, cyberattacks, disasters)
   - Legal / Compliance (lawsuits, SEBI/CCI actions, NCLT cases, tax disputes, environmental approvals/rejections)

2. Sectoral & Market Events
   - Industry Trends (IT spending, auto sales, FMCG pricing, real estate demand)
   - Commodity Movements (oil, coal, gold, silver, agriculture, monsoon impact)

3. Macroeconomic Events
   - RBI Policy (repo rate, CRR/SLR, liquidity measures, MPC decisions, RBI interventions)
   - Inflation / Growth Data (CPI, WPI, IIP, GDP, unemployment)
   - Trade & External Sector (exports, imports, current account, rupee-dollar, forex reserves)
   - Fiscal / Budgetary Policy (Union Budget, GST, subsidies, disinvestment, taxation, fiscal deficit)

4. Political & Policy Events
   - Government Decisions (cabinet approvals, infrastructure projects, PLI schemes, reforms, privatization)
   - Elections (state/national results, manifestos, coalition shifts, policy stances)
   - Protests / Strikes (farmer protests, labor strikes, civil unrest, industry shutdowns)

5. Geopolitical & Global Events
   - Conflicts / Wars / Border Tensions / Terror Attacks
   - Diplomatic / Trade Relations (India-US, India-China, BRICS, sanctions, FTAs, WTO disputes)
   - Global Central Bank Policy (Fed, ECB, BoJ actions affecting India)
   - OPEC & Oil Decisions (output cuts, embargoes, supply shocks)
   - Global Crises (pandemics, climate disasters, supply chain blockages like Suez/Red Sea)

6. Other
   - If the event does not fit above, still extract it with category "Other".

---
Output Format:
Return valid JSON. If multiple events, return an array of objects.

{
  "event_type": "One of the categories above",
  "event_name": "Concise 2–6 word title",
  "entities": {
    "companies": ["list of companies involved"],
    "people": ["executives, politicians, individuals"],
    "organizations": ["regulators, ministries, global orgs"]
  },
  "date": "Explicit date if present, else null",
  "location": "Country/region/state if available, else null",
  "amount": "Numeric or currency values (funding, deal size, GDP %, fine, etc.), else null",
  "sector": "Industry/sector (IT, banking, energy, FMCG, auto, agri, etc.)",
  "summary": "1–3 sentence plain-English explanation of the event",
  "confidence_score": "0–1 probability estimate of extraction accuracy"
}

---
Rules:
- Always normalize currency symbols (₹, $, €, etc.).
- Extract only explicit or strongly implied facts, no speculation.
- Keep event_name short and market-readable (e.g., "Infosys Q2 Earnings", "RBI Repo Hike", "India-China Border Clash").
- If one input has multiple events, output each as separate JSON objects inside an array.

---
Example Input:
"RBI hikes repo rate by 25 bps to 6.75 percent citing inflationary pressures."

Example Output:
{
  "event_type": "RBI Policy",
  "event_name": "RBI Repo Rate Hike",
  "entities": {
    "companies": [],
    "people": [],
    "organizations": ["RBI"]
  },
  "date": null,
  "location": "India",
  "amount": "25 bps; 6.75%",
  "sector": "Macroeconomy / Banking",
  "summary": "The Reserve Bank of India increased the repo rate by 25 basis points to 6.75%, citing rising inflation pressures.",
  "confidence_score": 0.96
}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Please extract the events from this text:\n\n{text}")
    ])
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    try:
        response = await chain.ainvoke({"text": text})
        return response.get("events", [])
    except Exception as e:
        print(f"Error extracting events: {e}")
        return []

def generate_brave_query(event: dict) -> str:
    """
    Generates a targeted Brave search query from an event object.
    """
    event_name = event.get("event_name", "")
    entities = " ".join([f'"{entity}"' for entity in event.get("entities", [])])
    sector = event.get("sector", "")

    query = f'"{event_name}" {entities} {sector} financial markets OR business OR news'
    return query
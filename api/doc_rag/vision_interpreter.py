import base64
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

llm = ChatOpenAI(temperature=0.2, model="gpt-4o")

async def describe_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

    prompt = ChatPromptTemplate.from_messages([
        ("human", [
            {"type": "text", "text": "Describe the following chart. Identify the chart type, title, axes, units, and extract the data into a markdown table. Provide a one-paragraph summary of the key insight."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}
        ])
    ])
    
    chain = prompt | llm 
    response = await chain.ainvoke({})
    return response.content
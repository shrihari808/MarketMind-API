import base64
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.callbacks import get_openai_callback
from token_logger import log_token_usage

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
    with get_openai_callback() as cb:
        response = await chain.ainvoke({})
        log_token_usage(
            model_name=llm.model_name,
            input_tokens=cb.prompt_tokens,
            output_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            purpose="document_image_description"
        )
    return response.content
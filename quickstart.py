import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
  api_key = os.environ["AZURE_OPENAI_API_KEY"],  
  base_url= os.environ["AZURE_OPENAI_API_V1_ENDPOINT"]
)

response = client.chat.completions.create(
  model="model-router",
    messages=[

        {"role": "user", "content": "Do you know the rules of Dungeons and Dragons?"}
    ]
)

#print(response)
print(response.model_dump_json(indent=2))
print(response.choices[0].message.content)
print(response.model)
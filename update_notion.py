from dotenv import load_dotenv
import os
import requests
import anthropic
import re
import json
import time

load_dotenv()

NOTION_API_KEY = os.getenv("api_key")
DATABASE_ID= os.getenv("database_url")
CLAUDE = os.getenv("claude")

client = anthropic.Anthropic(
    api_key=CLAUDE
)

# using at debugging
def get_database(database_id):
    url = f'https://api.notion.com/v1/databases/{database_id}'
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': '2022-06-28',
    }
    response = requests.get(url,headers=headers)
    
    return response.json()

def query_database(database_id):
    url = f'https://api.notion.com/v1/databases/{database_id}/query'
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }
    data = {
        "filter": {
            "and": [
                {
                    "property": "요약",
                    "rich_text": {
                        "is_empty": True
                    }
                },
                {
                    "property": "keyword",
                    "rich_text": {
                        "is_empty": True
                    }
                }
            ]
        }
    }
    response = requests.post(url, headers=headers,json=data)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(f"Error message: {response.text}")
        print(f"Request headers: {response.request.headers}")
        print(f"Request body: {response.request.body}")
    
    response.raise_for_status()
    
    with open('result.json','w') as file:
        file.write(json.dumps(response.json()))
    
    return response.json()['results']

def get_document_content(document_id):
    url = f'https://api.notion.com/v1/blocks/{document_id}/children'
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': '2022-06-28'
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    with open('page.json','w') as file:
        file.write(json.dumps(response.json()))
    
    document_content = response.json()['results']
    contents = False
    if document_content:
        entire_text = []
        
        for dic in document_content:
            dic_type = dic["type"]
            if dic_type == "paragraph":
                paragraph = []
                for para_dict in dic[dic_type]["rich_text"]:
                    paragraph.append(para_dict["plain_text"])
                entire_text.extend(paragraph)
                entire_text.append("\n")
            elif dic_type == 'image':
                pass
            else:
                if "rich_text" in dic[dic_type] and len(dic[dic_type]["rich_text"]) > 0:
                    plain_text = dic[dic_type]["rich_text"][0]["plain_text"]
                    entire_text.append(plain_text)
                    entire_text.append("\n")
                
        contents = "".join(entire_text)
        
    return contents

def update_page_properties(page_id, properties):
    summary, keyword = properties
    url = f'https://api.notion.com/v1/pages/{page_id}'
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }
    
    data = {
        'properties': {
            "요약": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": summary,
                            "link": None
                        }
                    }
                ]
            },
            "keyword": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": keyword,
                            "link": None
                        }
                    }
                ]
            }
        }
    }
    
    response = requests.patch(url, headers=headers, json=data)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(f"Error message: {response.text}")
        print(f"Request headers: {response.request.headers}")
        print(f"Request body: {response.request.body}")
        
    response.raise_for_status()
    print(f"{page_id} updated successfully!")


def extract_summary_and_keywords(text):
    summary_match = re.search(r'요약:(.*?)키워드:', text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else ''
    
    keywords_match = re.search(r'키워드:(.*)', text, re.DOTALL)
    keywords = keywords_match.group(1).strip() if keywords_match else ''

    return summary, keywords

def call_claude(article):
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        temperature=0.5,
        system=
        '''
        *** 
        you are native and fluent korean-english document assistant.
        Please extract 5 keywords from the following incoming user's input and also summarize them within 5 sentences.
        The input is normally documents like news, aritcle, paper etc... 
        
        Regardless of the user's input language type, you should leave the result in Korean.
        The result format is like below:
        *** 
        요약: [short summary here]
        
        키워드: keyword1,keyword2,keyword3,keyword4,keyword5
        ''',
        messages=[
            {"role":"user","content":article}
        ]
    )
    response = message.content
    
    response_text = ""
    for content_block in response:
        if content_block.type == "text":
            response_text += content_block.text + "\n"
    
    summary, keywords = extract_summary_and_keywords(response_text)
    return summary,keywords

def has_text_content(block):
    if block["type"] == "paragraph":
        return any(rt["plain_text"].strip() for rt in block["paragraph"]["rich_text"])
    else:
        return False

if __name__ == "__main__":
    documents = query_database(DATABASE_ID)
    
    for i in range(len(documents)):
        document_id = documents[i]['id']
        document_content = get_document_content(document_id)
        
        if document_content and document_content.strip():
                summary, keyword = call_claude(document_content)
                update_page_properties(document_id, (summary,keyword))
                time.sleep(10)
    
    print("task completed.")
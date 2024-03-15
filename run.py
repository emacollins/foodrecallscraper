import pandas as pd
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import prompts
import boto3
import json

def get_api_key(api_key_name: str) -> str:
    """Gets API key from AWS SSM

    Args:
        api_key_name (str): Name of API key in AWS SSM

    Returns:
        str: API key
    """
    ssm = boto3.client('ssm')
    response = ssm.get_parameter(Name=api_key_name, WithDecryption=True)
    return response['Parameter']['Value']

def fetch_and_parse_html(url: str) -> object:
    """Fetches HTML from URL and parses it with BeautifulSoup

    Args:
        url (str): URL link to fetch HTML from

    Returns:
        object: BeautifulSoup object
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.
    except requests.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
        return None
    except Exception as err:
        print(f'Other error occurred: {err}')
        return None
    else:
        return BeautifulSoup(response.text, 'html.parser')

def extract_data_from_row(row):
    cells = row.find_all("td")
    if len(cells) >= 6:  # Ensure there are enough cells to match your structure
        date = cells[0].text.strip()
        url = "https://www.fda.gov" + cells[1].find("a")["href"]
        brand = cells[1].text.strip()  # Assuming brand is in the 1st cell
        company_name = cells[5].text.strip()  # Assuming company name is in the 6th cell
        recall_reason = cells[4].text.strip()  # Assuming recall reason is in the 5th cell

        return {
            "date": date,
            "url": url,
            "brand": brand,
            "company_name": company_name,
            "recall_reason": recall_reason
        }
    else:
        return None

def get_summary_table(url: str, test_history: bool = False) -> pd.DataFrame:
    """Takes bs4.element.Tag object and parses out data
    for the current date

    Args:
        url (object): URL to fetch summary table from
        tet_history (bool): If True, fetches all recall data from first page, 
                            not just today's data
    Returns:
        pd.DataFrame: Dataframe with columns date, link, company_name, recall reason
    """
    # Iterate through each row of the table, skipping the header row
    soup = fetch_and_parse_html(url)
    table = soup.find("table", {"id": "datatable"})
    if table is None:
        print("Couldn't find the expected table")
        return None
    recall_data = [extract_data_from_row(row) for row in table.find_all("tr")[1:] if extract_data_from_row(row) is not None]
    today = pd.Timestamp.today().date()
    recall_data_df = pd.DataFrame(recall_data)
    recall_data_df["date"] = pd.to_datetime(recall_data_df['date']).dt.date
    if not test_history:
        recall_data_df = recall_data_df[recall_data_df['date'] == today]
    # All alergen alerts historically have "undeclared" in the recall reason
    recall_data_df = recall_data_df[recall_data_df["recall_reason"].str.lower().str.contains("undeclared|allergen")]
    return recall_data_df

def get_recall_announcement(url: str) -> str:
    """Gets company announcement of recall

    Args:
        url (str): URL to specific recall notice

    Returns:
        str: Recall announcement text
    """
    soup = fetch_and_parse_html(url)

    # Find the <h2> tag with id 'recall-announcement'
    h2_tag = soup.find('h2', id='recall-announcement')
    if h2_tag is None:
        print("Couldn't find the expected h2 tag")
        return None
    announcement_text = [h2_tag.text]
    announcement_text += [sibling.text for sibling in h2_tag.find_next_siblings() if sibling.name != "div"]
    return " ".join(announcement_text)

def get_num_states_impacted(summary_paragraph: str) -> int:
    """Use OpenAI API to get number of states impacted

    Args:
        summary_paragraph (str): Full recall notice

    Returns:
        int: Number of states impacted by recall
    """

    client = OpenAI(api_key=get_api_key(api_key_name='FDA_SCRAPER_OPENAI_API_KEY'))
    response = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    response_format={ "type": "json_object" },
    messages=[
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": summary_paragraph}
    ]
    )
    json_string = response.choices[0].message.content
    states_impacted = json.loads(json_string)["states_impacted"]
    return states_impacted

def main(test_history: bool = False) -> None:
    url = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
    recall_data_table = get_summary_table(url=url, test_history=test_history)
    recall_data_table["states_impacted"] = None
    for row in recall_data_table.itertuples():
        summary_paragraph = get_recall_announcement(row.url)
        states_impacted = get_num_states_impacted(summary_paragraph=summary_paragraph)
        recall_data_table.at[row.Index, "states_impacted"] = states_impacted
    recall_data_table.to_csv("recall_data.csv", index=False)

if __name__=="__main__":
    main(test_history=True)
import pandas as pd
import requests
from bs4 import BeautifulSoup

def get_summary_table(url: str) -> object:
    """Returns data from table on FDA page

    Args:
        url (str): URL of FDA page to scrape

    Returns:
        object: bs4.element.Tag
    """
    response = requests.get(url)
    webpage = response.content

    # Parse the HTML content
    soup = BeautifulSoup(webpage, "html.parser")
    table = soup.find("table", {"id": "datatable"})

    return table

def parse_summary_table(table: object) -> pd.DataFrame:
    """Takes bs4.element.Tag object and parses out data
    for the current date

    Args:
        table (object): bs4.element.Tag

    Returns:
        pd.DataFrame: Dataframe with columns date, link, company_name, recall reason
    """
    # Iterate through each row of the table, skipping the header row
    recall_data = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) >= 6:  # Ensure there are enough cells to match your structure
            date = cells[0].text.strip()
            link = "https://www.fda.gov" + cells[1].find("a")["href"]
            company_name = cells[5].text.strip()  # Assuming company name is in the 6th cell
            recall_reason = cells[4].text.strip()  # Assuming recall reason is in the 5th cell
            
            recall_data.append({
                "date": date,
                "link": link,
                "company_name": company_name,
                "recall_reason": recall_reason
            })
    today = pd.Timestamp.today()
    today = pd.Timestamp(year=2024, month=3, day=11) # TODO: Remove
    recall_data_df = pd.DataFrame(recall_data)
    recall_data_df["date"] = pd.to_datetime(recall_data_df['date'])
    filtered_df = recall_data_df[recall_data_df['date'] == today]
    return filtered_df

def parse_company_summary(url: str) -> str:
    """Gets summary from link to recall notice

    Args:
        url (str): Link to specific recall notice

    Returns:
        str: Summary of recall
    """
    response = requests.get(url)
    html_content = response.text

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the <h2> tag with id 'recall-announcement'
    h2_tag = soup.find('h2', id='recall-announcement')

    # Initialize an empty list to store paragraphs
    announcement_text = []

    # Add the h2 text to the list
    announcement_text.append(h2_tag.text)

    # Loop through the sibling elements of the h2 tag to find <p> tags
    for sibling in h2_tag.find_next_siblings():
        if sibling.name == 'p':
            announcement_text.append(sibling.text)
        else:
            break  # Stop if the next sibling is not a <p> tag
    return " ".join(announcement_text)        

def main() -> None:
    url = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
    summary_table = get_summary_table(url=url)
    recall_data_table = parse_summary_table(table=summary_table)
    for row in recall_data_table.itertuples()


if __name__=="__main__":
    main()
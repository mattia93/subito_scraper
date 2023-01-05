import bs4
import time
import requests
from os.path import join
import os
import datetime
from pandas import DataFrame
import pandas as pd
from discord_webhook import DiscordWebhook
import json
from decouple import config
from typing import Union, List


class COLNAMES:
    """
    Class that contains the column names of the DataFrame. It implements the Singleton pattern.
    """
    _instance = None

    def __new__(class_, *args, **kwargs):
        if class_._instance is None:
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance

    SEARCH = "search"
    DATE = "date"


class FIELDS:
    """
    Class that contains the fields of the search file. It implements the Singleton pattern.
    """

    _instance = None

    def __new__(class_, *args, **kwargs):
        if class_._instance is None:
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance

    STRING = "string"
    REGION = "region"
    PROVINCE = "province"
    CITY = "city"
    SEARCH_DESCRIPTION = "search_description"


def is_from_rivenditore(obj: bs4.element.Tag) -> bool:
    """
    Check if the object is from a dealer.

    Args:
        obj (bs4.element.Tag): The object to check.

    Returns:
        bool: true if the object is from a dealer, false otherwise.
    """
    spans = [
        span
        for span in obj.find_all("span")
        if span.text == "Rivenditore"
        or span.text == "Vetrina"
        or (span.has_attr("class") and "item-sold-badge" in span["class"])
    ]
    if len(spans) > 0:
        return True
    return False


def get_search_string(string: str) -> str:
    """
    Get the search string in html format.

    Args:
        string (str): The string to search.

    Returns:
        str: The search string in html format.
    """
    return string.replace(" ", "+")


def get_price(obj: bs4.element.Tag) -> Union[float, None]:
    """
    Get the price of the object.

    Args:
        obj (bs4.element.Tag): The object to check.

    Returns:
        Union[float, None]: The price of the object, None if the price is not specified.
    """
    price = obj.find("p", {"class": "price"}).get_text()
    try:
        price = float(price.split("\xa0")[0])
        return price
    except ValueError:
        return None


def is_in_price_range(
    obj: bs4.element.Tag, min_price: Union[float, None], max_price: Union[float, None]
) -> bool:
    """
    Check if the object is in the price range.

    Args:
        obj (bs4.element.Tag):
        min_price (Union[float, None]): Minimum price.
        max_price (Union[float, None]): Maximum price.

    Returns:
        bool: True if the object is in the price range, false otherwise.
    """
    price = get_price(obj)
    if price is None:
        return True
    if min_price == None:
        min_price = 0
    if max_price == None:
        max_price = 1000000
    if price >= min_price and price <= max_price:
        return True
    return False


def replace_month(date: str) -> str:
    """
    Replace the month in the date string.

    Args:
        date (str): The date string.

    Returns:
        str: The date string with the month replaced and the year set to the current year.
    """
    current_year = datetime.datetime.now().year
    date = date.replace("gen", f"01 {current_year}")
    date = date.replace("feb", f"02 {current_year}")
    date = date.replace("mar", f"03 {current_year}")
    date = date.replace("apr", f"04 {current_year}")
    date = date.replace("mag", f"05 {current_year}")
    date = date.replace("giu", f"06 {current_year}")
    date = date.replace("lug", f"07 {current_year}")
    date = date.replace("ago", f"08 {current_year}")
    date = date.replace("set", f"09 {current_year}")
    date = date.replace("ott", f"10 {current_year}")
    date = date.replace("nov", f"11 {current_year}")
    date = date.replace("dic", f"12 {current_year}")
    return date


def parse_date(date_str: str) -> datetime.datetime:
    """
    Parse the date string.

    Args:
        date_str (str): The date string.

    Returns:
        datetime.datetime: The parsed date.
    """
    date = date_str.replace("alle", "")
    date = date.replace("Oggi", datetime.datetime.now().strftime("%d %m %Y "))
    date = date.replace(
        "Ieri",
        (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d %m %Y "),
    )
    date = replace_month(date)
    date = datetime.datetime.strptime(date, "%d %m %Y  %H:%M")
    return date


def get_date(obj: bs4.element.Tag) -> Union[datetime.datetime, None]:
    """
    Get the date of the object.

    Args:
        obj (bs4.element.Tag): The object to check.

    Returns:
        Union[datetime.datetime, None]: The date of the object, None if the date is not specified.
    """
    try:
        city_span = obj.find("span", {"class": "city"})
        date_str = city_span.find_next_sibling("span").get_text()
        date = parse_date(date_str)
        return date
    except AttributeError:
        return None


def is_most_recent(obj: bs4.element.Tag, last_search: datetime.datetime) -> bool:
    """
    Check if the object is more recent than the last search.

    Args:
        obj (bs4.element.Tag): The object to check.
        last_search (datetime.datetime): The last search date.

    Returns:
        bool: True if the object is more recent than the last search, false otherwise.
    """
    date = get_date(obj)
    if date is None:
        return True
    return date > last_search


def change_spaces_to_dashes(string: str) -> str:
    """
    Change the spaces in the string to dashes.

    Args:
        string (str): The string to change.

    Returns:
        str: The string with the spaces changed to dashes.
    """
    return string.lower().replace(" ", "-")


def search_item(
    string: str,
    search_description: str,
    region: str = None,
    province: str = None,
    city: str = None,
    pages_number: int = 5,
    min_price: Union[float, None] = None,
    max_price: Union[float, None] = None,
    sleep_time: int = 5
) -> List[bs4.element.Tag]:
    """
    Search the item in the specified region, province and city.

    Args:
        string (str): string to search.
        search_description (str): string that represents the search.
        region (str, optional): Name of the region. Defaults to None.
        province (str, optional): Province of the region. Defaults to None.
        city (str, optional): City of the province. Defaults to None.
        pages_number (int, optional): Number of web pages to search. Defaults to 5.
        min_price (Union[float, None], optional): Minimum price. Defaults to None.
        max_price (Union[float, None], optional): Maximum price. Defaults to None.
        sleep_time (int, optional): Time to sleep between requests in seconds. Defaults to 5.

    Returns:
        List[bs4.element.Tag]: List of the objects found.
    """
    objects = []
    last_search = get_last_search_date(search_description)
    search_string = get_search_string(string)
    for page in range(1, pages_number + 1):
        if region is None:
            url = f"https://www.subito.it/annunci-italia/vendita/usato/?q={search_string}&o={page}"
        elif province is None:
            url = f"https://www.subito.it/annunci-{change_spaces_to_dashes(region)}/vendita/usato/?q={search_string}&o={page}"
        elif city is None:
            url = f"https://www.subito.it/annunci-{change_spaces_to_dashes(region)}/vendita/usato/{change_spaces_to_dashes(province)}/?q={search_string}&o={page}"
        else:
            url = f"https://www.subito.it/annunci-{change_spaces_to_dashes(region)}/vendita/usato/{change_spaces_to_dashes(province)}/{change_spaces_to_dashes(city)}/?q={search_string}&o={page}"
        data = requests.get(url)
        soup = bs4.BeautifulSoup(data.text, "html.parser")
        divs = soup.find_all("div", {"class": "item-card"})
        if page == 1 and len(divs) != 0:
            new_last_search = get_date(divs[0])
            write_last_search_date(search_description, new_last_search)
        for div in divs:
            if not (is_most_recent(div, last_search)):
                return objects
            if not (is_from_rivenditore(div)) and is_in_price_range(
                div, min_price, max_price
            ):
                objects.append(div)
        time.sleep(sleep_time)
    return objects


def get_last_search_date(
    string: str,
    filename: str = "last_searches_dates",
    target_folder: str = join("files", "csv"),
) -> datetime.datetime:
    """
    Get the last search date of the string. If the string is not found, return the current date at 00:00.

    Args:
        string (str): The string to search.
        filename (str, optional): Name of the file that contains the last search dates. Defaults to "last_searches_dates".
        target_folder (str, optional): Folder where the last searches file is located. Defaults to join("files", "csv").

    Returns:
        datetime.datetime: The last search date of the string.
    """
    filename = f"{filename}.csv"
    date = None
    if os.path.exists(join(target_folder, filename)):
        df = pd.read_csv(join(target_folder, filename))
        for i in range(len(df)):
            if string.strip() in df[COLNAMES.SEARCH][i].strip():
                date = datetime.datetime.strptime(
                    df[COLNAMES.DATE][i], "%Y-%m-%d %H:%M:%S"
                )
                break
    if date is None:
        now = datetime.datetime.now()
        return now - datetime.timedelta(
            minutes=now.hour * 60 + now.minute,
            seconds=now.second,
            microseconds=now.microsecond,
        )
    else:
        return date


def write_last_search_date(
    string: str,
    date: datetime.datetime,
    filename: str = "last_searches_dates",
    target_folder: str = join("files", "csv"),
) -> None:
    """
    Write the last search date of the string.

    Args:
        string (str): The string to search.
        date (datetime.datetime): The date to write.
        filename (str, optional): Name of the file that contains the last search dates. Defaults to "last_searches_dates".
        target_folder (str, optional): Folder where the last searches file is located. Defaults to join("files", "csv").
    """
    filename = f"{filename}.csv"
    os.mkdir(target_folder) if not os.path.exists(target_folder) else None
    if os.path.exists(join(target_folder, filename)):
        df = pd.read_csv(join(target_folder, filename), index_col=0)
        for i in range(len(df)):
            if string.strip() in df[COLNAMES.SEARCH][i].strip():
                df.loc[i][COLNAMES.DATE] = date
                df.to_csv(join(target_folder, filename))
                return
        df.loc[len(df)] = [string, date]
    else:
        df = DataFrame([[string, date]], columns=[COLNAMES.SEARCH, COLNAMES.DATE])
    df.to_csv(join(target_folder, filename))


def get_title(obj: bs4.element.Tag) -> Union[str, None]:
    """
    Get the title of the object.

    Args:
        obj (bs4.element.Tag): The object.

    Returns:
        Union[str, None]: The title of the object. None if the object has no title.
    """
    try:
        title = obj.find("h2").get_text()
        return title
    except AttributeError:
        return None


def get_link(obj: bs4.element.Tag) -> Union[str, None]:
    """
    Get the link of the object.

    Args:
        obj (bs4.element.Tag): The object.

    Returns:
        Union[str, None]: The link of the object. None if the object has no link.
    """
    try:
        link = obj.find("a")["href"]
        return link
    except AttributeError:
        return None


def get_image_url(obj: bs4.element.Tag) -> Union[str, None]:
    """
    Get the image url of the object.

    Args:
        obj (bs4.element.Tag): The object.

    Returns:
        Union[str, None]: The image url of the object. None if the object has no image url.
    """
    try:
        image_url = obj.find("img")["src"]
        return image_url
    except AttributeError:
        return None


def save_to_html(
    objects: list, filename: str, target_folder: str = join("files", "html")
) -> None:
    """
    Save the objects to an html file.

    Args:
        objects (list): List of objects to save.
        filename (str): Name of the HTML file.
        target_folder (str, optional): Folder where the HTML file will be saved. Defaults to join("files", "html").
    """
    os.mkdir(target_folder) if not os.path.exists(target_folder) else None
    with open(join(target_folder, f"{filename}.html"), "w") as f:
        f.write('<head><meta charset="utf-8"></head><body>')
        for o in objects:
            f.write(bs4.BeautifulSoup.prettify(o))
        f.write("</body>")


def send_as_discord_webhook(object: bs4.element.Tag, string: str):
    """
    Send the object as a Discord webhook.

    Args:
        object (bs4.element.Tag): The object to send.
        string (str): The string to search.
    """
    url = config("url")
    data_annuncio = get_date(object)
    prezzo_annuncio = f"{get_price(object)} €"
    titolo_annuncio = get_title(object)
    url_annuncio = get_link(object)
    img_annuncio = get_image_url(object)
    region = region if region is not None else "italia"
    username = "SubitBOT"
    avatar_url = "https://i.imgur.com/4M34hi2.png"
    content = f"Nuovo risultato per la ricerca: {string}"
    embeds = [
        {
            "title": f"{titolo_annuncio}",
            "url": f"{url_annuncio}",
            "color": 15258703,
            "fields": [
                {
                    "name": f"{prezzo_annuncio}",
                    "value": f"{data_annuncio}",
                },
            ],
            "image": {"url": f"{img_annuncio}"},
        }
    ]
    DiscordWebhook(
        url=url,
        content=content,
        username=username,
        avatar_url=avatar_url,
        embeds=embeds,
    ).execute()


def search_to_string(search: dict) -> str:
    """
    Convert the search dictionary to a string.

    Args:
        search (dict): The search dictionary.

    Returns:
        str: The search string.
    """
    search_string = f"{search[fields.STRING]}"
    search_string += f" {search[fields.REGION].replace(' ', '') if search[fields.REGION] is not None else 'italia'}"
    search_string += f" {search[fields.PROVINCE].replace(' ', '') if search[fields.PROVINCE] is not None else ''}"
    search_string += f" {search[fields.CITY].replace(' ', '') if search[fields.CITY] is not None else ''}"
    search_string = search_string.strip()
    return search_string


def populate_search(search: dict) -> dict:
    """
    Populate the search dictionary with None values and add the search description string.

    Args:
        search (dict): The search dictionary.

    Returns:
        dict: The populated search dictionary.
    """
    if fields.REGION not in search:
        search[fields.REGION] = None
    if fields.PROVINCE not in search:
        search[fields.PROVINCE] = None
    if fields.CITY not in search:
        search[fields.CITY] = None
    search[fields.SEARCH_DESCRIPTION] = search_to_string(search)
    return search


cols = COLNAMES()
fields = FIELDS()


if __name__ == "__main__":

    use_discord = config("use_discord", cast=bool, default=False)
    save_as_html = config("save_as_html", cast=bool, default=False)

    searches_file_path = config("searches_file", default="./files/json/search.json")

    with open(searches_file_path, "r") as f:
        searches = json.load(f)
        f.close()

    for search in searches:
        search = populate_search(search)
        objects = search_item(**search)
        
        if use_discord:
            for obj in objects:
                send_as_discord_webhook(obj, search[fields.SEARCH_DESCRIPTION])
                time.sleep(1)
        if save_as_html:
            save_to_html(objects, search[fields.SEARCH_DESCRIPTION])

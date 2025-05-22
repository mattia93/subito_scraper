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
    # price = obj.find("p", {"class": "price"}).get_text()
    price = obj.find("p", class_=lambda x: "price" in x).get_text()
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
        return datetime.datetime.now()


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
        agent = {"Accept" : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "it-IT,it;q=0.9",
                "Cookie": '__eoi=ID=b9c7a544a92dc432:T=1742897063:RT=1744363934:S=AA-AfjYwgHYeLEKRgB2WQ7rdxdaw; __gads=ID=12ebd7dbb4ff943b:T=1742897063:RT=1744363934:S=ALNI_MYDnfGMvhqDGhC-zip5bTWlOCvCNw; __gpi=UID=000010814555fefe:T=1742897063:RT=1744363934:S=ALNI_MaStPb7IAzGSGrpQG0ucgsseCntLg; FPID=FPID2.2.VoB%2Ffj%2FFTDiEI2W65BfZwQsSzaBs5m%2BDepDPmMcCH%2FI%3D.1742814851; _fbp=fb.1.1742897063917.132445923359654312; _ga_XXXXXXXXXX=GS1.1.1744362486.22.1.1744362519.0.0.324907197; _ga_D72SGH4DYJ=GS1.1.1744362486.22.1.1744362519.0.0.820200052; ttcsid_BUIJNV8M9N0HSM9DNOT0=1744362486375.6.1744362518161; kampyleSessionPageCounter=3; FPAU=1.1.1883419564.1742814851; _ga=GA1.1.410475542.1742897063; _pin_unauth=dWlkPU9HUTVZVEEyWldNdE5EUTNNUzAwT1RNNUxUZzJPRGN0TmpJMU1tSm1aR0l6TVRabA; _pulse2data=b6ae025a-4ba2-45cf-bcdf-a900dc08ad7b%2Cv%2C112705529%2C1744363417625%2CeyJpc3N1ZWRBdCI6IjIwMjUtMDMtMjVUMTA6MDQ6MjJaIiwiZW5jIjoiQTEyOENCQy1IUzI1NiIsImFsZyI6ImRpciIsImtpZCI6IjIifQ..TDMRLp4s2ILZdmbIMQe-Mg.R9oaIEkFitzW-6jWyhlf2og5M4dF4SqIRIzCX9GcZ9l64Ti6XnGsnFYfaUK6WAoGvMsyqC-cLw16Q8aadgucKDBupQpCOIBO3jlJNjhTIp9fvTdjDKvKxHvXs4GnrnJ9xVdrm44V3wkB3JIYpT5DJGIiRFke5i1W98OVGQSzWNaYGBblNkf3U3jPJLgMIRJzxPcK9c5WY1itAIw6yvBKkHfyJVsela95hKM9C4PllHU2ksTJF7VRcUxcC1thNoIE.clgIP0qamIVNqiY36jBXog%2C0%2C%2Ctrue%2C%2CeyJraWQiOiIyIiwiYWxnIjoiSFMyNTYifQ..1DVLkXOOlDuTUv-UzkP58A7GHsA5n5Iaf7BsRA7QFGg; _tt_enable_cookie=1; _ttp=01JQ6C5A36NAZS331Z950THAR7_.tt.1; ttcsid=1744362486376.6.1744362517951; w_page_view_counter=8; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%227UJG1AWIAZ00IrSlP7KP%22%2C%22expiryDate%22%3A%222026-04-11T09%3A08%3A37.680Z%22%7D; __rtbh.uid=%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22112705529%22%2C%22expiryDate%22%3A%222026-04-11T09%3A08%3A37.975Z%22%7D; _lr_atsDirect=; _lr_env=eyJ0aW1lc3RhbXAiOjE3NDQzNjI0ODYzODEsInZlcnNpb24iOiIxLjYuMCIsImVudmVsb3BlIjoiQW9XNm93cWJHLXptejd6aEZ2c0J6eEtLWmFOczlWZmJOUXVFSi1HRlpObFpxbEtqMVJGaUFGQk9CZTN4b0tyMm5ESDQtajVOWjRPTXR0OXl1UURsYnFyT1pISHphQl9NUkRmai1CcjRjdjJXN05Pa1g2ZDRkR1BUMWxJbmV0Mi02UHBEYldSbGxhOXc2RGpFYlRUbE5CWW1fY1Y4QUpGeF8tLWx2U2w1dWQtdHh6cjI5TDVNYkZwdkxDMnNSd09VdGV1RHJBdUoiLCJjcmVhdGlvblRpbWVzdGFtcCI6MTc0NDM2MjQ4NjM4MX0%3D; _lr_google_env=; _lr_pairId=eyJ0aW1lc3RhbXAiOjE3NDQzNjI0ODYzODIsInZlcnNpb24iOiIxLjYuMCIsImVudmVsb3BlIjpbIkF6b0ViOGVTc0pVUnliRFVvaFIzN0RMVStVVkF0RkNBRzFHNjYwYXY4TVNQIl0sImNyZWF0aW9uVGltZXN0YW1wIjoxNzQ0MzYyNDg2MzgyfQ%3D%3D; FPLC=cfCL4YUj90eEpbwDzENzjiqQP0GpDzuN3C2W%2BOxurBsf6FDui7mLrxr89trgECLBZwiXiFQL3Q5wkvGh8SHdBq3cbE7X%2FUieAiTXQVqckaeWcX7u%2BhO5X8BwjkrAWQ%3D%3D; crto_is_user_optout=false; crto_mapped_user_id=T82BVyo5SnKs0GGVQlKR-KLdaqxyen0U; cto_bundle=FWw3O19xQXlPMSUyRlJYb0RndFhNbkJRJTJCNUpWY2xDV3ZiSzZpZ3RLdGpnTCUyRkpPcEZtRTBYSU5RTWRTSHpGazkwdnFkWmN3SjhJaFlUeEhaelQ1NSUyQkNtbWdHWUVGZmhiaTdLZnVHcVNYZDclMkJxMCUyQjdvQWtsTFJ2RGNBdCUyRjUxcFRJZWF4WGl0; kampyleUserSession=1744362486531; kampyleUserSessionsCount=35; user_data={"id":"112705529","email":"bbd25278ebb0eda915af69b2b650eebdcbe8864f836d41d6454135771fd61730","name":"Mattia%20Chiari","ppid":"a32381eaa0d36172f091299466ea0fb3"}; _ga_VNNKRJLK19=GS1.1.1744205756.1.1.1744205830.0.0.0; bottega=mc1xf69f6544-ea6d-464e-a0d7-f721580d228c; _lr_geo_location=IT; _lr_geo_location_state=25; w_ad_view_counter=2; _lr_sampling_rate=100; _gcl_au=1.1.1815676088.1742897062; manageads.lastSeenBanner=228; _ga_XXXXXXXXXX=deleted; idl_env=Alu12u_lrJMCGXuKKZsXfnqJdvsayEzUdeZp_ArTGRhGnR-fx05aIOI26d8jJcwHE_SR0NRTRKhUIMdwffwp0RbjTznd5XcShyh3WbSYwbQ4VPkQBjeJiw0EVA6noNd4fMkxMb3PKggrEq9Da_TP0yHN85vgxP8NIfsoRAAJLC2BFxeJzDiXSWZJgoJbmOvI-YOY3M0P; idl_env_cst=IyyiLMcsQg%3D%3D; idl_env_last=Tue%2C%2001%20Apr%202025%2015%3A39%3A35%20GMT; __gsas=ID=edd0dac420d4d96a:T=1742897443:RT=1742897443:S=ALNI_MaaAk2dJR6Ls9HVN_3TtQJ_3jvo5w; kampyle_userid=50eb-48e7-279b-a380-0655-e84a-b6b1-f5a7; didomi_token=eyJ1c2VyX2lkIjoiMTk1Y2NjMmEtMWZiMS02ODczLWExYmYtNjIwNmQyMWIwOTE4IiwiY3JlYXRlZCI6IjIwMjUtMDMtMjVUMTA6MDQ6MjIuMzk1WiIsInVwZGF0ZWQiOiIyMDI1LTAzLTI1VDEwOjA0OjIzLjc0MFoiLCJ2ZW5kb3JzIjp7ImVuYWJsZWQiOlsiZ29vZ2xlIiwiYzphbXBsaXR1ZGUiLCJjOm1pY3Jvc29mdC1vbmVkcml2ZS1saXZlLXNkayIsImM6YXBwc2ZseWVyLTlqY3duaVk5IiwiYzpiaW5nLWFkcyIsImM6cm9ja2V0LWZ1ZWwiLCJjOnJhZGl1bW9uZSIsImM6YWR2ZXJ0aXNpbmdjb20iLCJjOmtydXgtZGlnaXRhbCIsImM6eWFob28tYWQtZXhjaGFuZ2UiLCJjOnlhaG9vLWFuYWx5dGljcyIsImM6cXVhbnRjYXN0LW1lYXN1cmVtZW50IiwiYzp5YWhvby1hZC1tYW5hZ2VyLXBsdXMiLCJjOm9tbml0dXJlLWFkb2JlLWFuYWx5dGljcyIsImM6YWRwaWxvdGNvbm5lY3RhZCIsImM6Z3JhcGVzaG90IiwiYzpxdWFudHVtLWFkdmVydGlzaW5nIiwiYzpicmlnaHRyb2xsIiwiYzp4MSIsImM6dHViZW1vZ3VsIiwiYzpzZWdtZW50IiwiYzpha2FtYWktY29va2llLXN5bmMiLCJjOmFjY29yZGFudC1tZWRpYSIsImM6YWRtb2IiLCJjOmFvbC1jZG4iLCJjOm1lZGFsbGlhLWloenJ5RkxZIiwiYzpzYWxlc2ZvcmNlLUNQQkZFZkhQIiwiYzpvcHRpbWl6ZWx5LUVOUUVpaVpUIiwiYzpha2FjZG9yb2QtV0FEN2lYdGgiLCJjOm1pY3Jvc29mdC1hbmFseXRpY3MiLCJjOnR1cmJvIiwiYzp0aWt0b2stS1pBVVFMWjkiLCJjOmF0aW50ZXJuZS1jV1FLSGVKWiIsImM6Ymx1ZWthaSIsImM6Z29vZ2xlYW5hLTRUWG5KaWdSIiwiYzpzb2Npb21hbnRpLW1NVEc4eGc0IiwiYzphd3MtY2xvdWRmcm9udCIsImM6eWFob28tZ2VtaW5pLWFuZC1mbHVycnkiLCJjOnN1YmxpbWVzay1wWjdBbnk3RyIsImM6bWVldHJpY3NnLU5kRU44V3hUIiwiYzpjZW50cm8taVVXVm1ONE4iLCJjOm1pY3Jvc29mdCIsImM6aGF2YXNtZWRpLUJBRzdwSkRlIiwiYzpwaW50ZXJlc3QiLCJjOnNwb3R4aW5jLXdpQ0VmTHluIiwiYzptZWRpYW1hdGgtd0pRd1RBWjIiLCJjOmRpZG9taSJdfSwicHVycG9zZXMiOnsiZW5hYmxlZCI6WyJnZW9sb2NhdGlvbl9kYXRhIiwiZGV2aWNlX2NoYXJhY3RlcmlzdGljcyIsImNvb2tpZWFuYS1rQ0NSR3o0bSIsImNvb2tpZWRpLW5OZTIzUWpkIiwiY29va2lldGVjLTlxZkFFVndrIiwiYXVkaWVuY2VtLXhlZGVVMmdRIl19LCJ2ZW5kb3JzX2xpIjp7ImVuYWJsZWQiOlsiZ29vZ2xlIiwiYzp0dXJibyJdfSwidmVyc2lvbiI6MiwiYWMiOiJEQnlBWUFFWUFMSUNTd0pSQVVWQkxHQ2VjRkNNTFJndEhCZWlEQmNHRGdBQS5EQnlBWUFFWUFMSUNTd0pSQVVWQkxHQ2VjRkNNTFJndEhCZWlEQmNHRGdBQSJ9; euconsent-v2=CQO03QAQO03QAAHABBENBiFsAP_gAEPgABCYJQEB5C5cASFCACp0AOsAAYUHQFAAAkAABAIBASABAIIAIIQEgGAQIAAAAAAAAAIAICQAAAAgAAAAAQAAAAAAIAAAAACQAAAAIAAAAAABAQAAAAAAAIAAEAAAgEAAAAAAgAAAAAIACEgAAAAAAAAAAAAAAAAFAAAAAAAAAAAIAAAIACgEAAAAAAAAAAAAABAIBAAAAAAEEb4D4ACwAKgAXAA4AB4AEAAKgAZAA0ACOAEwAKEAXABdADEAHoAPwAhABHADKAH6AQgAi0BHAEdAPaAmIBTYC8wGTgMsAfuBG8AA.f_wACHwAAAAA; displayCookieConsent=y; kppid=CEECBF5FAEE446C579E97271; akacd_orodha=2177452799~rv=84~id=266e8d35553f88f7c2926592bf4ed0f4',
                "Priority": "u=0, i",
                "Referer": "https://www.subito.it/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15"}
        data = requests.get(url, headers=agent)
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
    region = "italia"
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


def run():
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


if __name__ == "__main__":
    run()
import bs4
import time
import requests
from os.path import join, dirname
import os
import datetime
from pandas import DataFrame
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
import json
from decouple import config

class COLNAMES:
    _instance = None
    def __new__(class_, *args, **kwargs):
        if class_._instance is None:
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance
    SEARCH = "search"
    DATE = "date"


def is_from_rivenditore(obj: bs4.element.Tag):
    spans = [span for span in obj.find_all("span") if span.text == "Rivenditore" or span.text == "Vetrina" or (span.has_attr('class') and "item-sold-badge" in span['class'])] 
    if len(spans) > 0:
        return True
    return False


def get_search_string(string: str):
    return string.replace(" ", "+")


def get_price(obj: bs4.element.Tag):
    price = obj.find("p", {"class": "price"}).get_text()
    try:
        price = float(price.split("\xa0")[0])
        return price
    except ValueError:
        return None

def is_in_price_range(obj: bs4.element.Tag, min_price: int, max_price: int):
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


def replace_month(date: str):
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


def parse_date(date_str: str):
    date = date_str.replace("alle", "")
    date = date.replace("Oggi", datetime.datetime.now().strftime("%d %m %Y "))
    date = date.replace("Ieri", (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d %m %Y "))
    date = replace_month(date)
    date = datetime.datetime.strptime(date, "%d %m %Y  %H:%M")
    return date

def get_date(obj: bs4.element.Tag):
    try:
        city_span = obj.find('span', {'class': "city"})
        date_str = city_span.find_next_sibling('span').get_text()
        date = parse_date(date_str)
        return date 
    except AttributeError:
        return None

def is_most_recent(obj: bs4.element.Tag, last_search: datetime.datetime):
    date = get_date(obj)
    if date is None:
        return True
    return date > last_search



def search_item(
    string: str,
    pages_number: int = 5,
    min_price: int = None,
    max_price: int = None,
    sleep_time: int = 5,
):
    objects = []
    last_search = get_last_search_date(string)
    search_string = get_search_string(string)
    for page in range(1, pages_number + 1):
        url = f"https://www.subito.it/annunci-lombardia/vendita/usato/brescia/?q={search_string}&o={page}"

        data = requests.get(url)
        soup = bs4.BeautifulSoup(data.text, "html.parser")
        divs = soup.find_all("div", {"class": "item-card"})
        objects.extend(
            [
                div
                for div in divs
                if not (is_from_rivenditore(div))
                and is_in_price_range(div, min_price, max_price)
                and is_most_recent(div, last_search)
            ]
        )
        if not is_most_recent(divs[-1], last_search):
            break
        time.sleep(sleep_time)
    return objects

def get_last_search_date(string: str, filename: str = 'last_searches_dates', target_folder: str = join('files', "csv")):
    filename = f"{filename}.csv"
    date = None
    if os.path.exists(join(target_folder, filename)):
        df = pd.read_csv(join(target_folder, filename))
        for i in range(len(df)):
            if string.strip() in df[COLNAMES.SEARCH][i].strip():
                date = datetime.datetime.strptime(df[COLNAMES.DATE][i], "%Y-%m-%d %H:%M:%S.%f")
                break
    now = datetime.datetime.now()
    write_last_search_date(string, now)
    if date is None:
        return now - datetime.timedelta(minutes= now.hour*60 + now.minute, seconds=now.second, microseconds=now.microsecond)
    else:
        return date

def write_last_search_date(string: str, date: datetime.datetime, filename: str = 'last_searches_dates', target_folder: str = join('files', "csv")):
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


def get_title(obj: bs4.element.Tag):
    try:
        title = obj.find("h2").get_text()
        return title
    except AttributeError:
        return None

def get_link(obj: bs4.element.Tag):
    try:
        link = obj.find("a")["href"]
        return link
    except AttributeError:
        return None

def get_image_url(obj: bs4.element.Tag):
    try:
        image_url = obj.find("img")["src"]
        return image_url
    except AttributeError:
        return None
            

def save_as_html(objects: list, filename: str, target_folder: str = join('files', "html")):
    with open(join(target_folder, f"{filename}.html"), "w") as f:
        f.write('<head><meta charset="utf-8"></head><body>')
        for o in objects:
            f.write(bs4.BeautifulSoup.prettify(o))
        f.write("</body>")

def send_as_discord_webhook(object: bs4.element.Tag, string: str):
    url = config("url")
    data_annuncio = get_date(object)
    prezzo_annuncio = f'{get_price(object)} €'
    titolo_annuncio = get_title(object)
    url_annuncio = get_link(object)
    img_annuncio = get_image_url(object)
    username = "SubitBOT"
    avatar_url = "https://i.imgur.com/4M34hi2.png"
    content = f"Nuovo risultato per la ricerca: {string}"
    embeds = [
        {
            "title": f"{titolo_annuncio}",
            "url": f"{url_annuncio}",
            "color": 15258703,
            "fields":[
                {
                "name": f"{prezzo_annuncio}",
                "value": f"{data_annuncio}",
                },

            ],
            "image": {
                "url": f"{img_annuncio}"
            }
        }
    ]
    DiscordWebhook(url=url, content=content, username=username, avatar_url=avatar_url, embeds=embeds).execute()


cols = COLNAMES()


if __name__ == "__main__":
    searches = [
        ["iphone 11", 10, 250, 400],
        ["iphone 12", 10, 350, 550],
    ]

    for search in searches:
        objects = search_item(*search)
        for obj in objects:
            send_as_discord_webhook(obj, search[0])
            time.sleep(1)
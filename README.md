# Subito.it web scraper

## Description
This  is a web scraper script for the website [subito.it](https://www.subito.it). The script lets you filter the available insertions by prices ranges, automatically removing resellers and stores. The selected insertions can be saved as an HTML file or as a Discord Webhook message. 

## Install

The installation requires [Anaconda](https://www.anaconda.com/download/).
Run the following command to install the Anaconda environment
```bash
cd subito-scraper
conda env create -n bs --file bs.yml
source activate bs
python code/scraper.py
```

## Usage
### Edit search.json file
The `search.json` file contains the search parameters. You can edit it with the following command:
```bash
vim files/json/search.json
```

You can edit the search parameters like this:
```json
[
    {
        "name": "search1",
        "min_price": 100,
        "max_price": 200
    },
    {
        "name": "search2",
        "min_price": null,
        "max_price": 300
    },
    {
        "name": "search3",
        "min_price": 400,
        "max_price": null
    }
]
```

### Usage with Discord webhook
In order to send the results to a discord channel, you need to specify the webhook url in the `.env` file.
Run the following command to edit the `.env` file:

```bash
vim .env
```

You can then add your url variable like this:
```txt
url=https://discordapp.com/api/webhooks/...
searches_file_path="./files/json/search.json"
use_discord=true
save_as_html=false
```

### Usage with html file
If you want to use the html file instead of the discord webhook, you need to change the variable `use_discord` in the `.env` file to `false` and the variable `save_as_html` to `true`.

```bash
vim .env
```

You can then add your url variable like this:
```txt
searches_file_path="./files/json/search.json"
use_discord=false
save_as_html=true
```
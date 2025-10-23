# 🚀 LinkHunt 

**New in this version:**  
Integrated **OpenAI GPT-powered Cover Letter Generation** directly into the web app.  
See the section **“Configuring `config.json`”** below to enable it.

---

## 🧠 Overview — LinkedIn Job Scraper & Tracker

**LinkHunt** is a Python application that scrapes LinkedIn job postings and stores them in a local **SQLite** database or **CSV** file.  
It also includes a sleek **Flask web interface** where you can browse, search, and manage your job applications — marking each as *Applied*, *Interview*, *Rejected*, or *Hidden*.

![Screenshot](./screenshot/screenshot1.png)

---

## 💡 Why This Exists

If you’ve ever searched for jobs on LinkedIn, you know how painful it can be:

- 🔁 The same jobs keep reappearing in every search  
- 🚫 Sponsored and irrelevant postings clutter the feed  
- 🤯 It’s hard to track what you’ve already applied to  

**LinkHunt** fixes that by letting you:

- ✅ Scrape non-sponsored LinkedIn job posts  
- 🧩 Store data locally in CSV or SQLite  
- 🔍 Filter by keywords in **title** or **description**  
- 📅 Sort strictly by **date posted**  
- 🗂️ Track your application status easily (Applied / Interview / Rejected / Hidden)

No duplicates. No spam. Just the jobs you actually want to see.

---

## ⚠️ Important Notice

> **Disclaimer:** LinkedIn does **not officially permit scraping** of its platform.  
Use this project **only for personal or educational purposes**.  
If you plan to scrape frequently, it’s recommended to use **proxy servers** or **rotating IPs** to avoid being blocked by LinkedIn.

---
### Prerequisites

- Python 3.6 or higher
- Flask
- Requests
- BeautifulSoup
- Pandas
- SQLite3
- Pysocks

### Installation

1. Clone the repository to your local machine.
2. Install the required packages using pip: `pip install -r requirements.txt`
3. Create a `config.json` file in the root directory of the project. See the `config.json` section below for details on the configuration options. Config_example.json is provided as an example, feel free to use it as a template.
4. Run the scraper using the command `python main.py`. Note: run this first first to populate the database with job postings prior to running app.py.
4. Run the application using the command `python app.py`.
5. Open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.

### Usage

The application consists of two main components: the scraper and the web interface.

#### Scraper

The scraper logic lives in **`scraper/core.py`** and is triggered via **`main.py`**.  
It collects job postings from LinkedIn using the search queries and filters defined in `config.json`.  
After scraping, it removes duplicates and irrelevant results based on your keyword filters, then stores the cleaned data in a local **SQLite database** (`data/my_database.db`) and/or CSV file.


To run the scraper, execute the following command:

```
python main.py
```

#### Web Interface

The web interface is powered by Flask and implemented in app.py, using routes from webapp/routes.py and UI templates in webapp/templates/.
It provides a clean dashboard to browse, search, and manage the scraped jobs.

You can mark jobs as:

Applied 🟦 (highlighted in blue)

Interview 🟩 (highlighted in green)

Rejected 🟥 (highlighted in red)

Hidden ⚫ (removed from view)

To run the web interface, execute the following command:

```
python app.py
```

Then, open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.

### Configuration

The `config.json` file contains the configuration options for the scraper and the web interface. Below is a description of each option:

- proxies – Proxy configuration for the requests library. Example:
"proxies": {"http": "http://yourproxy:port", "https": "https://yourproxy:port"}

- headers – HTTP headers used in requests. Set a valid User-Agent to mimic a browser.

- db_path – Path to the SQLite database file (e.g., data/my_database.db).

- jobs_tablename – Table name for storing scraped jobs.

- filtered_jobs_tablename – Table name for filtered jobs.

- pages_to_scrape – Number of LinkedIn pages to scrape for each query.

- rounds – How many times to rerun each search to increase coverage.

- days_toscrape – Ignore job posts older than this number of days.

- OpenAI Integration (optional)

- OpenAI_API_KEY – Your OpenAI API key from platform.openai.com.

- OpenAI_Model – Model for cover letter generation. gpt-4 gives the best results, gpt-3.5-turbo is cheaper.

- resume_path – Path to your resume in PDF format. Use a single-column layout for best parsing accuracy.

Search and Filter Options

- search_queries – A list of search objects:

- keywords – Search terms for job titles.

- location – City or region for the search.

- f_WT – Work type filter (0 onsite, 1 hybrid, 2 remote, or empty for all).

- title_include – Keep jobs containing any of these words in the title.

- title_exclude – Remove jobs containing any of these words in the title.

- desc_words – Exclude jobs whose descriptions contain these keywords.

- company_exclude – Filter out specific companies.

- languages – Only include jobs in certain languages (e.g., “en”, “de”, “fr”). Leave empty for all.

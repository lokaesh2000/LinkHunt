# scraper/core.py
import requests
import json
import sqlite3
import sys
from sqlite3 import Error
from bs4 import BeautifulSoup
import time as tm
from itertools import groupby
from datetime import datetime, timedelta, time
import pandas as pd
from urllib.parse import quote
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

# ----------------------------
# Config & HTTP helpers
# ----------------------------

def load_config(file_name):
    with open(file_name, "r", encoding="utf-8") as f:
        return json.load(f)

def get_with_retry(url, config, retries=3, delay=1):
    for _ in range(retries):
        try:
            if len(config.get("proxies", {})) > 0:
                r = requests.get(
                    url,
                    headers=config.get("headers", {}),
                    proxies=config.get("proxies", {}),
                    timeout=5,
                )
            else:
                r = requests.get(
                    url,
                    headers=config.get("headers", {}),
                    timeout=5,
                )
            return BeautifulSoup(r.content, "html.parser")
        except requests.exceptions.Timeout:
            print(f"Timeout occurred for URL: {url}, retrying in {delay}s...")
            tm.sleep(delay)
        except Exception as e:
            print(f"An error occurred while retrieving the URL: {url}, error: {e}")
    return None

# ----------------------------
# Transform helpers
# ----------------------------

def transform(soup):
    # Parse job cards from search results soup
    joblist = []
    try:
        divs = soup.find_all("div", class_="base-search-card__info")
    except Exception:
        print("Empty page, no jobs found")
        return joblist

    for item in divs:
        title = item.find("h3").text.strip()
        company = item.find("a", class_="hidden-nested-link")
        location = item.find("span", class_="job-search-card__location")
        parent_div = item.parent
        entity_urn = parent_div.get("data-entity-urn", "")
        job_posting_id = entity_urn.split(":")[-1] if entity_urn else ""
        job_url = f"https://www.linkedin.com/jobs/view/{job_posting_id}/" if job_posting_id else ""

        date_tag_new = item.find("time", class_="job-search-card__listdate--new")
        date_tag = item.find("time", class_="job-search-card__listdate")
        date = date_tag["datetime"] if date_tag else date_tag_new["datetime"] if date_tag_new else ""

        job_description = ""
        job = {
            "title": title,
            "company": company.text.strip().replace("\n", " ") if company else "",
            "location": location.text.strip() if location else "",
            "date": date,
            "job_url": job_url,
            "job_description": job_description,
            "applied": 0,
            "hidden": 0,
            "interview": 0,
            "rejected": 0,
        }
        joblist.append(job)

    return joblist

def transform_job(soup):
    if soup is None:
        return "Could not find Job Description"
    div = soup.find("div", class_="description__text description__text--rich")
    if div:
        # Remove unwanted elements
        for element in div.find_all(["span", "a"]):
            element.decompose()

        # Replace bullet points
        for ul in div.find_all("ul"):
            for li in ul.find_all("li"):
                li.insert(0, "-")

        text = div.get_text(separator="\n").strip()
        text = text.replace("\n\n", "")
        text = text.replace("::marker", "-")
        text = text.replace("-\n", "- ")
        text = text.replace("Show less", "").replace("Show more", "")
        return text
    else:
        return "Could not find Job Description"

def safe_detect(text):
    try:
        return detect(text)
    except LangDetectException:
        return "en"

def remove_irrelevant_jobs(joblist, config):
    # Filter by description, title include/exclude, language, and company exclude
    new_joblist = [
        job
        for job in joblist
        if not any(word.lower() in job["job_description"].lower() for word in config.get("desc_words", []))
    ]
    if len(config.get("title_exclude", [])) > 0:
        new_joblist = [
            job
            for job in new_joblist
            if not any(word.lower() in job["title"].lower() for word in config["title_exclude"])
        ]
    if len(config.get("title_include", [])) > 0:
        new_joblist = [
            job
            for job in new_joblist
            if any(word.lower() in job["title"].lower() for word in config["title_include"])
        ]
    if len(config.get("languages", [])) > 0:
        new_joblist = [
            job
            for job in new_joblist
            if safe_detect(job["job_description"]) in config["languages"]
        ]
    if len(config.get("company_exclude", [])) > 0:
        new_joblist = [
            job
            for job in new_joblist
            if not any(word.lower() in job["company"].lower() for word in config["company_exclude"])
        ]
    return new_joblist

def remove_duplicates(joblist, _config):
    # Duplicate by same title + company
    joblist.sort(key=lambda x: (x["title"], x["company"]))
    joblist = [next(g) for _, g in groupby(joblist, key=lambda x: (x["title"], x["company"]))]
    return joblist

def convert_date_format(date_string):
    """
    Converts a date string (YYYY-MM-DD) to a date object.
    Returns None if conversion fails.
    """
    date_format = "%Y-%m-%d"
    try:
        job_date = datetime.strptime(date_string, date_format).date()
        return job_date
    except ValueError:
        print(f"Error: The date for job {date_string} - is not in the correct format.")
        return None

# ----------------------------
# Database helpers
# ----------------------------

def create_connection(config):
    conn = None
    path = config["db_path"]
    try:
        conn = sqlite3.connect(path)
    except Error as e:
        print(e)
    return conn

def create_table(conn, df, table_name):
    # Create table with explicit types and insert rows
    type_mapping = {
        "int64": "INTEGER",
        "float64": "REAL",
        "datetime64[ns]": "TIMESTAMP",
        "object": "TEXT",
        "bool": "INTEGER",
    }

    columns_with_types = ", ".join(
        f'"{column}" {type_mapping[str(df.dtypes[column])]}'
        for column in df.columns
    )

    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_with_types}
        );
    """

    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()

    insert_sql = f"""
        INSERT INTO "{table_name}" ({', '.join(f'"{column}"' for column in df.columns)})
        VALUES ({', '.join(['?' for _ in df.columns])})
    """
    for record in df.to_dict(orient="records"):
        cursor.execute(insert_sql, list(record.values()))
    conn.commit()

    print(f"Created the {table_name} table and added {len(df)} records")

def update_table(conn, df, table_name):
    # Append only new rows compared to existing table
    df_existing = pd.read_sql(f"select * from {table_name}", conn)

    # Records unique in df relative to df_existing on (title, company, date)
    df_new_records = pd.concat([df, df_existing, df_existing]).drop_duplicates(
        ["title", "company", "date"], keep=False
    )

    if len(df_new_records) > 0:
        df_new_records.to_sql(table_name, conn, if_exists="append", index=False)
        print(f"Added {len(df_new_records)} new records to the {table_name} table")
    else:
        print(f"No new records to add to the {table_name} table")

def table_exists(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone()[0] == 1

# ----------------------------
# De-dup against DB
# ----------------------------

def job_exists(df, job):
    if df.empty:
        return False
    # Either same URL or same (title, company, date)
    return (df["job_url"] == job["job_url"]).any() or (
        ((df["title"] == job["title"]) & (df["company"] == job["company"]) & (df["date"] == job["date"])).any()
    )

def get_jobcards(config):
    all_jobs = []
    for _ in range(0, config["rounds"]):
        for query in config["search_queries"]:
            keywords = quote(query["keywords"])
            location = quote(query["location"])
            for i in range(0, config["pages_to_scrape"]):
                url = (
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={keywords}"
                    f"&location={location}"
                    f"&f_TPR=&f_WT={query.get('f_WT','')}"
                    f"&geoId=&f_TPR={config.get('timespan','')}"
                    f"&start={25*i}"
                )
                soup = get_with_retry(url, config)
                jobs = transform(soup) if soup else []
                all_jobs = all_jobs + jobs
                print("Finished scraping page: ", url)

    print("Total job cards scraped: ", len(all_jobs))
    all_jobs = remove_duplicates(all_jobs, config)
    print("Total job cards after removing duplicates: ", len(all_jobs))
    all_jobs = remove_irrelevant_jobs(all_jobs, config)
    print("Total job cards after removing irrelevant jobs: ", len(all_jobs))
    return all_jobs

def find_new_jobs(all_jobs, conn, config):
    # Only keep jobs not already present in either jobs or filtered_jobs tables
    jobs_tablename = config["jobs_tablename"]
    filtered_jobs_tablename = config["filtered_jobs_tablename"]

    jobs_db = pd.DataFrame()
    filtered_jobs_db = pd.DataFrame()

    if conn is not None:
        if table_exists(conn, jobs_tablename):
            query = f"SELECT * FROM {jobs_tablename}"
            jobs_db = pd.read_sql_query(query, conn)
        if table_exists(conn, filtered_jobs_tablename):
            query = f"SELECT * FROM {filtered_jobs_tablename}"
            filtered_jobs_db = pd.read_sql_query(query, conn)

    new_joblist = [
        job
        for job in all_jobs
        if not job_exists(jobs_db, job) and not job_exists(filtered_jobs_db, job)
    ]
    return new_joblist

# ----------------------------
# Orchestration (original flow)
# ----------------------------

def main(config_file):
    start_time = tm.perf_counter()
    job_list = []

    config = load_config(config_file)
    jobs_tablename = config["jobs_tablename"]
    filtered_jobs_tablename = config["filtered_jobs_tablename"]

    # 1) Scrape search results and parse job cards
    all_jobs = get_jobcards(config)

    # 2) DB connection
    conn = create_connection(config)

    # 3) Filter out jobs already in DB
    all_jobs = find_new_jobs(all_jobs, conn, config)
    print("Total new jobs found after comparing to the database: ", len(all_jobs))

    # 4) For each new job, fetch full description and language
    if len(all_jobs) > 0:
        for job in all_jobs:
            job_date = convert_date_format(job["date"])
            if job_date:
                job_date = datetime.combine(job_date, time())
                # Skip if older than X days
                if job_date < datetime.now() - timedelta(days=config["days_to_scrape"]):
                    continue

            print("Found new job: ", job["title"], "at ", job["company"], job["job_url"])
            desc_soup = get_with_retry(job["job_url"], config)
            job["job_description"] = transform_job(desc_soup)
            language = safe_detect(job["job_description"])
            if language not in config["languages"]:
                print("Job description language not supported: ", language)
            job_list.append(job)

        # 5) Final filtering by description/title/language/etc.
        jobs_to_add = remove_irrelevant_jobs(job_list, config)
        print("Total jobs to add: ", len(jobs_to_add))

        # 6) Complement for filtered table
        filtered_list = [job for job in job_list if job not in jobs_to_add]

        # 7) DataFrames & date_loaded
        df = pd.DataFrame(jobs_to_add)
        df_filtered = pd.DataFrame(filtered_list)
        now_str = datetime.now().astype(str) if hasattr(datetime.now(), "astype") else str(datetime.now())
        if not df.empty:
            df["date_loaded"] = str(datetime.now())
        if not df_filtered.empty:
            df_filtered["date_loaded"] = str(datetime.now())

        # 8) Persist to DB
        if conn is not None:
            if not df.empty:
                if table_exists(conn, jobs_tablename):
                    update_table(conn, df, jobs_tablename)
                else:
                    create_table(conn, df, jobs_tablename)

            if not df_filtered.empty:
                if table_exists(conn, filtered_jobs_tablename):
                    update_table(conn, df_filtered, filtered_jobs_tablename)
                else:
                    create_table(conn, df_filtered, filtered_jobs_tablename)
        else:
            print("Error! cannot create the database connection.")

        # 9) CSV outputs
        if not df.empty:
            df.to_csv("linkedin_jobs.csv", index=False, encoding="utf-8")
        if not df_filtered.empty:
            df_filtered.to_csv("linkedin_jobs_filtered.csv", index=False, encoding="utf-8")
    else:
        print("No jobs found")

    end_time = tm.perf_counter()
    print(f"Scraping finished in {end_time - start_time:.2f} seconds")

def run_scraper():
    # Keep the original entry convention
    config_file = "config.json"
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
    main(config_file)

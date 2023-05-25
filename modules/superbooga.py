from bs4 import BeautifulSoup
from .chromadb import add_chunks_to_collector, make_collector
from .download_urls import download_urls
from modules import chat, shared
import re
import requests
from io import BytesIO
import tempfile

collector = make_collector()
chat_collector = make_collector()
chunk_count = 5


def custom_generate_instruct_prompt(user_input, chunk_count, **kwargs):
    results = collector.get_sorted(user_input, n_results=chunk_count)
    user_input = "### Memory:\n" + "\n".join(results) + "\n" + user_input
    return user_input


def feed_data_into_collector(corpus, chunk_len, chunk_sep):
    global collector
    # Defining variables
    chunk_len = int(chunk_len)
    chunk_sep = chunk_sep.replace(r"\n", "\n")
    cumulative = ""

    # Breaking the data into chunks and adding those to the db
    cumulative += "Breaking the input dataset...\n\n"
    yield cumulative
    if chunk_sep:
        data_chunks = corpus.split(chunk_sep)
        data_chunks = [
            [
                data_chunk[i : i + chunk_len]
                for i in range(0, len(data_chunk), chunk_len)
            ]
            for data_chunk in data_chunks
        ]
        data_chunks = [x for y in data_chunks for x in y]
    else:
        data_chunks = [
            corpus[i : i + chunk_len] for i in range(0, len(corpus), chunk_len)
        ]

    cumulative += f"{len(data_chunks)} chunks have been found.\n\nAdding the chunks to the database...\n\n"
    yield cumulative
    add_chunks_to_collector(data_chunks, collector)
    cumulative += "Done."
    yield cumulative



import PyPDF2
import os
from mimetypes import guess_type
def feed_url_file_into_collector(url, chunk_len, chunk_sep):
    yield "Downloading the file from the URL...\n\n"
    response = requests.get(url)
    if response.status_code == 200:
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_name = temp_file.name

        # Write the content to the temporary file
        with open(temp_file_name, 'wb') as f:
            f.write(response.content)

        yield "File downloaded successfully...\n\n"
        
        text = ''
        
        # Guess the MIME type of the file
        

        if temp_file_name.endswith(".pdf"):
            # The file is a PDF
            pdf_file_obj = open(temp_file_name, 'rb')
            pdf_reader = PyPDF2.PdfFileReader(pdf_file_obj)
            for page_num in range(pdf_reader.numPages):
                page_obj = pdf_reader.getPage(page_num)
                text += page_obj.extractText()
            pdf_file_obj.close()
        else:
            # Assume the file is a text file
            with open(temp_file_name, 'r', errors='ignore') as f:
                text = f.read()

        os.unlink(temp_file_name)  # delete the temporary file

        for i in feed_data_into_collector(text, chunk_len, chunk_sep):
            yield i
    else:
        yield "Failed to download the file.\n\n"


def feed_file_into_collector(file, chunk_len, chunk_sep):
    yield "Reading the input dataset...\n\n"
    text = file.decode("utf-8")
    for i in feed_data_into_collector(text, chunk_len, chunk_sep):
        yield i


def feed_url_into_collector(urls, chunk_len, chunk_sep, strong_cleanup, threads):
    all_text = ""
    cumulative = ""

    urls = urls.strip().split("\n")
    cumulative += f"Loading {len(urls)} URLs with {threads} threads...\n\n"
    yield cumulative
    for update, contents in download_urls(urls, threads=threads):
        yield cumulative + update

    cumulative += "Processing the HTML sources..."
    yield cumulative
    for content in contents:
        soup = BeautifulSoup(content, features="html.parser")
        for script in soup(["script", "style"]):
            script.extract()

        strings = soup.stripped_strings
        if strong_cleanup:
            strings = [s for s in strings if re.search("[A-Za-z] ", s)]

        text = "\n".join([s.strip() for s in strings])
        all_text += text

    for i in feed_data_into_collector(all_text, chunk_len, chunk_sep):
        yield i


def apply_settings(_chunk_count):
    global chunk_count
    chunk_count = int(_chunk_count)
    settings_to_display = {
        "chunk_count": chunk_count,
    }

    yield f"The following settings are now active: {str(settings_to_display)}"


def remove_special_tokens(string):
    pattern = r"(<\|begin-user-input\|>|<\|end-user-input\|>|<\|injection-point\|>)"
    return re.sub(pattern, "", string)


def input_modifier(string):
    if shared.is_chat():
        return string

    # Find the user input
    pattern = re.compile(r"<\|begin-user-input\|>(.*?)<\|end-user-input\|>", re.DOTALL)
    match = re.search(pattern, string)
    if match:
        user_input = match.group(1).strip()

        # Get the most similar chunks
        results = collector.get_sorted(user_input, n_results=chunk_count)

        # Make the injection
        string = string.replace("<|injection-point|>", "\n".join(results))

    return remove_special_tokens(string)

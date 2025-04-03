import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_mistralai.chat_models import ChatMistralAI
import logging
from src.prompt import query_uniprot, generate_solr_query
import io
from contextlib import redirect_stdout
import sqlite3
import time 
import torch
import pandas as pd
from datetime import datetime
import sys
import os
from src.prott5Embedder import getEmbeddings
from src.prott5Embedder import getT5Model
from annoy import AnnoyIndex
import requests


device = torch.device('cuda:3' if torch.cuda.is_available() else 'cpu')

model_dir = None
transformer_link = "Rostlab/prot_t5_xl_half_uniref50-enc"
model, tokenizer = getT5Model(model_dir, transformer_link)

def fetch_data_from_db(query, params=None):
    with sqlite3.connect('protein_index.db') as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        data = cur.fetchall()
    return data

def runSql(dbPath, query):
    conn = sqlite3.connect(dbPath)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_uniprot_protein_info(protein_id):
    url = f"https://rest.uniprot.org/uniprotkb/{protein_id}.json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            protein_name = data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "N/A")
            genes = data.get("genes", [])
            gene_symbol = genes[0].get("geneName", {}).get("value", "N/A") if genes else "N/A"
            
            return protein_name, gene_symbol
        else:
            return "N/A", "N/A"
    except Exception:
        return "N/A", "N/A"

def searchSpecificEmbedding(embedding):
    annoydb = 'asset/protein_embeddings.ann'  
    embeddingDimension = 1024  

    annoy_index = AnnoyIndex(embeddingDimension, 'euclidean')
    annoy_index.load(annoydb)

    neighbors, distances = annoy_index.get_nns_by_vector(embedding, 5, include_distances=True)

    results = []
    for index_id, distance in zip(neighbors, distances):
        protein_id_df = runSql("protein_index.db", f"SELECT protein_id FROM id_map WHERE index_id = {index_id}")
        if not protein_id_df.empty:
            protein_id = protein_id_df.iloc[0]['protein_id']
            protein_name, gene_symbol = get_uniprot_protein_info(protein_id)

            results.append({
                'protein_id': protein_id,  
                'distance': distance,
                'protein_name': protein_name,
                'gene_symbol': gene_symbol
            })

    return pd.DataFrame(results)

# Initialize logging stream in session state if not already present
if 'log_stream' not in st.session_state:
    st.session_state.log_stream = io.StringIO()

# Configure logging
logging.basicConfig(stream=st.session_state.log_stream, level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Set up the Streamlit page configuration
st.set_page_config(page_title="UniProt KB Query Interface", layout="wide")

# Mode selection buttons
mode = st.radio("Select Mode", ["LLM Query", "Vector Search"], horizontal=True)

# Get queryfields, result fields and searchfields from files, store them in session state so that they are not recalculated on every rerun
with st.spinner("Loading required fields..."):
    if 'queryfields' not in st.session_state:
        with open("asset/queryfields.txt", "r") as f:
            st.session_state.queryfields = f.read()
    if 'searchfields' not in st.session_state:
        st.session_state.searchfields = fetch_data_from_db("SELECT * FROM search_fields")
    if 'resultfields' not in st.session_state:
        st.session_state.resultfields = fetch_data_from_db("SELECT * FROM result_fields")

if mode == "LLM Query":

    st.title("🧬 UniProt KB LLM Query Interface v0.21")

    model_choices = [
        "gemini-pro", "gemini-1.5-flash", "gpt-4o-mini", "gpt-4o",
        "claude-3-5-sonnet-20240620", "meta/llama-3.1-405b-instruct",
        "mistral-small", "codestral-latest"
    ]

    # Streamlit form
    with st.form("query_form"):
        # LLM selection
        llm_type = st.selectbox("Select LLM Type", model_choices)

        # API Key input
        api_key = st.text_input("Enter your API Key", type="password")

        # Verbose mode
        verbose = st.checkbox("Enable verbose mode")

        # Return limit
        limit = st.number_input("Set return limit", min_value=1, max_value=100, value=5)

        # retry count
        retry_count = st.number_input("Set retry count", min_value=1, value=10)

        question = st.text_input("Enter your question about proteins:", placeholder="e.g., What proteins are related to Alzheimer's disease?")

        # Submit button
        submitted = st.form_submit_button("Search")

        # counter func
        def retries_counter(question, llm, searchfields, queryfields, resultfields, limit, retry_count):
            
            temp_solr = ""
            temp_result = ""
            status_placeholder = st.empty()
            current_attempt = 1
            total_count = retry_count

            while retry_count > 0:
                status_placeholder.info(f"Attempt {current_attempt} for query '{question}'...")

                try:
                    solr_query = generate_solr_query(question, llm, searchfields, queryfields, resultfields)
                    
                    results = query_uniprot(solr_query, limit)

                    if results.get('results'):
                        status_placeholder.success(f"Results found on attempt {current_attempt}.")
                        return solr_query, results
                    else:
                        temp_solr = solr_query
                        temp_result = results
                        if current_attempt == total_count:
                            status_placeholder.error(f"No results found for query '{question}' after {total_count} attempts.")
                        else:
                            status_placeholder.warning(f"No results found on attempt {current_attempt}.")
                except Exception as e:
                    status_placeholder.error(f"Error on attempt {current_attempt}: {str(e)}")
                    if temp_solr:
                        solr_query = temp_solr
                    else:
                        solr_query = "ERROR"
                        temp_result = {"results": []}

                current_attempt += 1
                retry_count -= 1
                time.sleep(3)  

            # Return last attempt's Solr query and result (empty if no success)
            #st.error(f"No results found for query '{question}' after {total_count} attempts.")
            return temp_solr or "ERROR", temp_result

    if submitted:
        if question and api_key:
            try:
                # Clear log stream
                st.session_state.log_stream.seek(0)
                st.session_state.log_stream.truncate()

                # Set up LLM based on selection and API key
                if llm_type in ["gemini-pro", "gemini-1.5-flash"]:
                    llm = GoogleGenerativeAI(model=llm_type, google_api_key=api_key)
                elif llm_type in ["gpt-4o", "gpt-4o-mini"]:
                    llm = ChatOpenAI(model=llm_type, api_key=api_key)
                elif llm_type == "claude-3-5-sonnet-20240620":
                    llm = ChatAnthropic(model=llm_type, anthropic_api_key=api_key)
                elif llm_type == "meta/llama-3.1-405b-instruct":
                    llm = ChatNVIDIA(model=llm_type, api_key=api_key)
                elif llm_type in ["mistral-small", "codestral-latest"]:
                    llm = ChatMistralAI(model=llm_type, api_key=api_key)

                if verbose:
                    logger.info(f"Using LLM: {llm_type}")
                    logger.info(f"Question: {question}")
                    logger.info(f"Limited to {limit} results")

                with st.spinner("Generating query and fetching results..."):
                    #solr_query = generate_solr_query(question, llm, st.session_state.searchfields, st.session_state.queryfields, st.session_state.resultfields)
                    
                    solr_query, results = retries_counter(
                        question,
                        llm,
                        st.session_state.searchfields,
                        st.session_state.queryfields,
                        st.session_state.resultfields,
                        limit,
                        retry_count
                    )
                    
                    st.subheader("Generated Solr Query:")
                    st.code(solr_query)
                    if verbose:
                        logger.info(f"Generated Solr query: {solr_query}")

                    #results = query_uniprot(solr_query, limit)

                    st.subheader("Results:")
                    for item in results.get('results', []):
                        with st.expander(f"{item['entryType']}: {item['primaryAccession']}"):
                            st.write(f"**Protein Name:** {item.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', 'N/A')}")
                            st.write(f"**UniProt KB Entry Link:** [https://www.uniprot.org/uniprotkb/{item.get('primaryAccession', 'N/A')}]")
                            st.write(f"**Gene:** {item.get('genes', [{}])[0].get('geneName', {}).get('value', 'N/A')}")
                            st.write(f"**Organism:** {item.get('organism', {}).get('scientificName', 'N/A')}")
                            st.write(f"**Function:** {item.get('comments', [{}])[0].get('texts', [{}])[0].get('value', 'N/A') if item.get('comments') else 'N/A'}")

                    if verbose:
                        st.subheader("Debug Logs:")
                        st.code(st.session_state.log_stream.getvalue())
                    
                    if verbose:
                        st.subheader("Full Query Result:")
                        st.json(results)
                        
                    time.sleep(5)

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                if verbose:
                    logger.error(f"Error details: {str(e)}", exc_info=True)
        elif not api_key:
            st.warning("Please enter your API key.")
        elif not question:
            st.warning("Please enter a question.")

    st.sidebar.title("About")
    st.sidebar.info(
        "This app allows you to query the UniProt KB database using natural language. "
        "It converts your question into a Solr query using a Language Model and fetches relevant protein information."
    )

elif mode == "Vector Search":
    st.title("🔎 Vector Search")

    with st.form("vector_search_form"):
        sequence_input = st.text_area(
            "Enter your protein sequence:",
            placeholder="e.g., MKTFFVAGVLAALATA..."
        )

        search_button = st.form_submit_button("Search")

    if search_button:
        if sequence_input:
            st.subheader("Search Results:")
            st.write("🔄 Searching for similar protein sequences...")
            
            sequence_dict = {"query_protein": sequence_input}
            startTimeToCreateEmbedding = datetime.now()
            embDict, tempDict = getEmbeddings(sequence_dict, model_dir, per_protein=True)
            endTimeToCreateEmbedding = datetime.now()

            query_embedding = embDict["query_protein"]

            startTimeToFindByEmbedding = datetime.now()
            foundEmbeddings = searchSpecificEmbedding(query_embedding)
            endTimeToFindByEmbedding = datetime.now()

            embeddingTime = endTimeToCreateEmbedding - startTimeToCreateEmbedding
            searchTime = endTimeToFindByEmbedding - startTimeToFindByEmbedding

            st.write("✅ Embedding process completed!")
            st.write(f"⏳ Embedding time: {embeddingTime.total_seconds()} seconds")
            st.write(f"🔍 Search time: {searchTime.total_seconds()} seconds")

            if foundEmbeddings.empty:
                st.warning("❌ No similar proteins found.")
            else:
                st.success("✅ Similar proteins found!")
                st.write(f"Distance Metric: Euclidean")
                foundEmbeddings["protein_id"] = foundEmbeddings["protein_id"].apply(
                lambda pid: f'<a href="https://www.uniprot.org/uniprotkb/{pid}" target="_blank">{pid}</a>')
                st.write(foundEmbeddings.to_html(escape=False), unsafe_allow_html=True)
        else:
            st.warning("Please enter a protein sequence.")

    st.sidebar.title("About")
    st.sidebar.info(
        "This app allows you to query the UniProt KB database using natural language. "
        "It converts your question into a Solr query using a Language Model and fetches relevant protein information."
    )

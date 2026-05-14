from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import os
import uvicorn
from queries import (
    GET_SCALES,
    QUERY_RELATION,
    FETCH_EVALUATION_DETAILS,
    FETCH_QUESTIONS,
    FETCH_ANSWERS
)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

app = FastAPI()

class QueryParams(BaseModel):
    client: str        # UUID agora
    evaluationid: int  # id da evaluation


def get_scales():
    with engine.connect() as conn:
        result = conn.execute(text(GET_SCALES))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df.to_dict(orient='records')


def query_relation(client, evaluationid, scale_id):
    with engine.connect() as conn:
        result = conn.execute(text(QUERY_RELATION), {
            'client': client,
            'evaluation_id': evaluationid,
            'scale_id': scale_id
        })
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def fetch_evaluation_details(evaluation_id, client, scale_id):
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_EVALUATION_DETAILS), {
            'evaluation_id': evaluation_id,
            'client': client,
            'scale_id': scale_id
        })
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def fetch_questions(scale_id):
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_QUESTIONS), {'scale_id': scale_id})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def fetch_answers(client, evaluationid, scale_id):
    params = {
        'client': client,
        'evaluationid': evaluationid,
        'scale_id': scale_id
    }
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_ANSWERS), params)
        return pd.DataFrame(result.fetchall(), columns=result.keys())


@app.get("/")
async def root():
    return {"message": "Welcome to the Recommendation API (new schema)!"}


@app.get("/list_scales")
async def list_scales():
    return get_scales()


@app.get("/recommend")
async def recommend_questions_route(evaluation: int, client: str, scale: int):
    evaluationid = evaluation

    # Verificar se avaliação existe
    evaluation_row = query_relation(client, evaluationid, scale)
    if evaluation_row.empty:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    df_primary_answers = fetch_answers(
        client=client,
        evaluationid=evaluationid,
        scale_id=scale
    )

    df_questions = fetch_questions(scale_id=scale)

    pivot_table = df_primary_answers.pivot_table(
        index='evaluationid',
        columns='questionid',
        values='score',
        fill_value=0
    )

    matrix = pivot_table.values
    similarity_matrix = cosine_similarity(matrix)

    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=pivot_table.index,
        columns=pivot_table.index
    )

    similarity_scores = similarity_df.loc[evaluationid]
    top_similarities = similarity_scores.sort_values(ascending=False).head(5)
    top_similarities = top_similarities.drop(evaluationid, errors='ignore')
    similar_ids = top_similarities.index.tolist()

    clients_df = df_primary_answers[['evaluationid', 'client_fk']].drop_duplicates()
    clients_df = clients_df.set_index('evaluationid')
    similar_clients = clients_df.loc[similar_ids]

    results = []
    for sim in similar_clients.itertuples():
        details = fetch_evaluation_details(
            evaluation_id=sim.Index,
            client=sim.client_fk,
            scale_id=scale
        )
        if not details.empty:
            results.append(details.to_dict(orient='records'))

    return {"similar": results}
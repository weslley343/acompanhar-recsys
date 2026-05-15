from fastapi import FastAPI, HTTPException, Depends
from auth import professional_only, TokenPayload
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import os
import uvicorn
from typing import Literal
from queries import (
    GET_SCALES,
    QUERY_RELATION,
    FETCH_EVALUATION_DETAILS,
    FETCH_QUESTIONS,
    FETCH_ANSWERS,
    FETCH_CLIENTS_FROM_EVALUATIONS,
    FETCH_FULL_HISTORY
)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

app = FastAPI()

class QueryParams(BaseModel):
    client: str                                  # UUID do cliente
    evaluationid: int                            # ID da avaliação
    scale: int                                   # ID da escala
    ntop_similarity: int = Field(5, ge=1, le=10)      # Top N clientes similares (1-10)
    ntop_recommendations: int = Field(5, ge=1, le=10) # Top N perguntas recomendadas (1-10)
    days_window: Literal[7, 30, 60] = 30              # Janela de análise em dias (7, 30 ou 60)


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


def fetch_answers(client, evaluationid, scale_id, limit=1000):
    params = {
        'client': client,
        'evaluationid': evaluationid,
        'scale_id': scale_id,
        'limit': limit
    }
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_ANSWERS), params)
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def get_similar_evaluations(evaluation_ids):
    """
    Simula entrada vinda do seu backend FastAPI
    """
    return evaluation_ids


def fetch_clients_from_evaluations(evaluation_ids):
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_CLIENTS_FROM_EVALUATIONS), {"ids": evaluation_ids})
        clients = [row[0] for row in result.fetchall()]
    return clients


def fetch_full_history(clients):
    with engine.connect() as conn:
        result = conn.execute(text(FETCH_FULL_HISTORY), {"clients": clients})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df


@app.get("/")
async def root():
    return {"message": "Welcome to the Recommendation API (new schema)!"}


@app.get("/list_scales")
async def list_scales():
    return get_scales()


@app.post("/recommend")
async def recommend_questions_route(
    params: QueryParams, 
    user: TokenPayload = Depends(professional_only)
):
    evaluationid = params.evaluationid
    client = params.client
    scale = params.scale
    ntop_sim = params.ntop_similarity
    ntop_rec = params.ntop_recommendations
    window_days = params.days_window

    print(f"\n--- Iniciando recomendação ---")
    print(f"Params: evaluation={evaluationid}, client={client}, scale={scale}")
    print(f"Config: ntop_sim={ntop_sim}, ntop_rec={ntop_rec}, days_window={window_days}")

    # Verificar se avaliação existe
    evaluation_row = query_relation(client, evaluationid, scale)
    if evaluation_row.empty:
        print("Erro: Avaliação não encontrada no banco.")
        raise HTTPException(status_code=404, detail="Evaluation not found")

    df_primary_answers = fetch_answers(
        client=client,
        evaluationid=evaluationid,
        scale_id=scale
    )
    print(f"Respostas buscadas: {len(df_primary_answers)} linhas.")

    df_questions = fetch_questions(scale_id=scale)

    pivot_table = df_primary_answers.pivot_table(
        index='evaluationid',
        columns='questionid',
        values='score',
        fill_value=0 #apenas para o caso de haver algum valor nulo, muito improvável
    )

    matrix = pivot_table.values
    similarity_matrix = cosine_similarity(matrix)

    similarity_df = pd.DataFrame(
        similarity_matrix,
        index=pivot_table.index,
        columns=pivot_table.index
    )

    # Criar um DataFrame com os scores de similaridade para a avaliação atual
    similarity_scores = similarity_df.loc[evaluationid].to_frame(name='score')
    
    # Cruzamos com as informações de cliente
    clients_df = df_primary_answers[['evaluationid', 'client_fk']].drop_duplicates()
    clients_df = clients_df.set_index('evaluationid')
    
    similarity_with_clients = similarity_scores.join(clients_df)
    
    # Removemos a própria avaliação da lista de busca
    similarity_with_clients = similarity_with_clients.drop(evaluationid, errors='ignore')
    
    # Ordenamos pela maior similaridade e removemos duplicatas de cliente, 
    # mantendo apenas a avaliação mais parecida de cada pessoa
    top_similarities = (similarity_with_clients
                        .sort_values(by='score', ascending=False)
                        .drop_duplicates(subset='client_fk')
                        .head(ntop_sim))
    
    print(f"Top {len(top_similarities)} avaliações similares encontradas.")

    # Lógica interna solicitada: busca de clientes e histórico completo
    similar_evaluation_ids = top_similarities.index.tolist()
    clients = fetch_clients_from_evaluations(similar_evaluation_ids)
    print(f"Buscando histórico para {len(clients)} clientes similares.")
    df_history = fetch_full_history(clients)
    print(f"Histórico total carregado: {len(df_history)} linhas.")
    
    # Implementação da janela de tempo (lógica interna)
    df_history['timestamp'] = pd.to_datetime(df_history['timestamp'])
    
    # Criar mapeamento de IDs de avaliação para timestamps para consulta rápida
    timestamps = df_history.set_index("evaluationid")["timestamp"].to_dict()
    
    # Obter os timestamps e clientes das avaliações alvo
    eval_targets_mask = df_history['evaluationid'].isin(similar_evaluation_ids)
    evaluations_targets = df_history[eval_targets_mask][['evaluationid', 'timestamp', 'client_fk']].drop_duplicates()
    
    filtered_list = []
    for _, row in evaluations_targets.iterrows():
        eval_id = row['evaluationid']
        eval_time = row['timestamp']
        client_id = row['client_fk']
        window_end = eval_time + pd.Timedelta(days=window_days)
        
        # Filtrar avaliações do MESMO cliente dentro da janela
        mask = (df_history['client_fk'] == client_id) & (df_history['timestamp'] > eval_time) & (df_history['timestamp'] <= window_end)
        
        filtered_df = df_history[mask].copy()
        filtered_df['target_evaluation'] = eval_id
        filtered_list.append(filtered_df)
        
    if filtered_list:
        df_30d_after = pd.concat(filtered_list, ignore_index=True)
    else:
        df_30d_after = pd.DataFrame()
    print(f"Avaliações na janela de {window_days} dias: {len(df_30d_after)} linhas.")

    # Agrupar por cliente para processamento individual
    dfs_por_cliente = {client: df_30d_after[df_30d_after["client_fk"] == client].copy()
                       for client in df_30d_after["client_fk"].unique()}
    print(f"Dados agrupados para {len(dfs_por_cliente)} clientes.")

    # Criar matrizes de questões por avaliações para cada cliente
    matrizes_por_cliente = {}
    for client, df_client in dfs_por_cliente.items():
        matriz = df_client.pivot_table(
            index="questionid",
            columns="evaluationid",
            values="score",
            aggfunc="mean"
        )
        matrizes_por_cliente[client] = matriz
    print(f"Matrizes individuais criadas.")

    # Calcular as matrizes delta (evolução dos scores) por cliente
    matrizes_delta_por_cliente = {}
    for client, matriz in matrizes_por_cliente.items():
        # Ordenar colunas pelas avaliações
        matriz_ordenada = matriz.sort_index(axis=1)

        # Calcular o delta
        matriz_delta = matriz_ordenada.diff(axis=1)

        # Preencher apenas a primeira coluna com 0
        if not matriz_delta.empty:
            primeira_coluna = matriz_delta.columns[0]
            matriz_delta[primeira_coluna] = 0

        matrizes_delta_por_cliente[client] = matriz_delta
    print(f"Matrizes delta calculadas.")

    # Calcular coeficientes de intensidade de mudança por cliente
    coeficientes_por_cliente = {}
    for client, matriz_delta in matrizes_delta_por_cliente.items():
        matriz = matriz_delta.copy()
        # Criar df de coeficientes em float
        coef = pd.DataFrame(
            data=np.zeros((matriz.shape[0], matriz.shape[1])),
            index=matriz.index,
            columns=matriz.columns,
            dtype=float
        )
        # Para cada questão
        for questao in matriz.index:
            last_change_eval = None
            for eval_id in matriz.columns:
                delta = matriz.loc[questao, eval_id]
                if delta == 0:
                    coef.loc[questao, eval_id] = 0.0
                    continue
                # Timestamp atual
                t_atual = timestamps[eval_id]
                # Timestamp de referência
                if last_change_eval is None:
                    t_ref = timestamps[matriz.columns[0]]
                else:
                    t_ref = timestamps[last_change_eval]
                delta_t = (t_atual - t_ref).total_seconds() / 86400.0
                coef_val = (delta_t / abs(delta)) * (1 if delta > 0 else -1)
                coef.loc[questao, eval_id] = float(coef_val)
                last_change_eval = eval_id
        coeficientes_por_cliente[client] = coef
    print(f"Coeficientes de intensidade calculados.")

    # Agregar coeficientes por pergunta para cada cliente
    somas_por_cliente = {}
    for client, coef_matrix in coeficientes_por_cliente.items():
        # Soma por linha (questionid)
        somas_por_cliente[client] = coef_matrix.sum(axis=1)
    print(f"Somas por cliente finalizadas.")

    # Calcular soma global de coeficientes e obter o Top N solicitado
    if somas_por_cliente:
        soma_global = pd.concat(somas_por_cliente.values()).groupby(level=0).sum()
        top_n_res = soma_global.sort_values().head(ntop_rec)
        print(f"\n--- Top {len(top_n_res)} Recomendações ---")
        top_recommendations = []
        for q_id, score in top_n_res.items():
            print(f"Question: {q_id}, Intensity Score: {score:.4f}")
            top_recommendations.append({
                "questionid": int(q_id),
                "intensity_score": float(score)
            })
    else:
        print("Aviso: Nenhuma recomendação gerada (somas vazias).")
        top_recommendations = []

    print(f"--- Fim da recomendação para evaluation {evaluationid} ---\n")
    return {
        "evaluation_id": evaluationid,
        "recommendations": top_recommendations
    }
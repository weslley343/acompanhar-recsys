# Busca todas as escalas disponíveis (id e nome)
GET_SCALES = "SELECT id, name FROM scales;"

# Verifica se uma avaliação específica pertence a um cliente e escala informados
QUERY_RELATION = """
SELECT *
FROM evaluations
WHERE client_fk = :client
  AND id = :evaluation_id
  AND scale_fk = :scale_id;
"""

# Busca as respostas de avaliações futuras (id maior que o atual) do mesmo cliente e escala
FETCH_EVALUATION_DETAILS = """
SELECT
    evaluations.id AS evaluationid,
    evaluations.client_fk,
    questions.id AS questionid,
    itens.score,
    evaluations.created_at AS timestamp
FROM evaluations
INNER JOIN answers ON evaluations.id = answers.evaluation_fk
INNER JOIN itens ON itens.id = answers.item_fk
INNER JOIN questions ON questions.id = answers.question_fk
WHERE evaluations.id > :evaluation_id
  AND evaluations.client_fk = :client
  AND evaluations.scale_fk = :scale_id;
"""

# Lista todas as perguntas vinculadas a uma escala específica
FETCH_QUESTIONS = """
SELECT
    id AS questionid,
    item_order,
    content
FROM questions
WHERE scale_fk = :scale_id;
"""

# Busca todas as respostas da escala para montar a matriz de similaridade,
# incluindo a avaliação atual e excluindo outras avaliações do mesmo cliente.
FETCH_ANSWERS = """
WITH answers_cte AS (
    SELECT
        evaluations.id AS evaluationid,
        evaluations.client_fk,
        questions.id AS questionid,
        itens.score,
        evaluations.created_at AS timestamp
    FROM evaluations
    INNER JOIN answers ON evaluations.id = answers.evaluation_fk
    INNER JOIN itens ON itens.id = answers.item_fk
    INNER JOIN questions ON questions.id = answers.question_fk
    WHERE questions.scale_fk = :scale_id
)
SELECT *
FROM answers_cte
WHERE client_fk != :client
   OR evaluationid = :evaluationid;
"""

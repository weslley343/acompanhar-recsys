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

# Busca as respostas da avaliação imediatamente posterior (pelo timestamp) do mesmo cliente e escala
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
WHERE evaluations.id = (
    SELECT id
    FROM evaluations
    WHERE client_fk = :client
      AND scale_fk = :scale_id
      AND created_at > (SELECT created_at FROM evaluations WHERE id = :evaluation_id)
    ORDER BY created_at ASC
    LIMIT 1
);
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

# Busca as respostas das avaliações mais recentes para montar a matriz de similaridade.
# Inclui obrigatoriamente a avaliação atual e limita o total de outras avaliações.
FETCH_ANSWERS = """
WITH selected_evaluations AS (
    -- Avaliação atual
    SELECT id FROM evaluations WHERE id = :evaluationid
    UNION
    -- X avaliações mais recentes de outros clientes
    (SELECT id FROM evaluations
     WHERE scale_fk = :scale_id AND client_fk != :client
     ORDER BY created_at DESC
     LIMIT :limit)
)
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
WHERE evaluations.id IN (SELECT id FROM selected_evaluations);
"""

# Busca os IDs únicos de clientes a partir de uma lista de IDs de avaliação
FETCH_CLIENTS_FROM_EVALUATIONS = """
SELECT DISTINCT client_fk
FROM evaluations
WHERE id = ANY(:ids);
"""

# Busca o histórico completo de avaliações e respostas de uma lista de clientes
FETCH_FULL_HISTORY = """
SELECT
    evaluations.id AS evaluationid,
    evaluations.client_fk,
    evaluations.created_at AS timestamp,
    questions.id AS questionid,
    itens.score
FROM evaluations
INNER JOIN answers ON evaluations.id = answers.evaluation_fk
INNER JOIN itens ON itens.id = answers.item_fk
INNER JOIN questions ON questions.id = answers.question_fk
WHERE evaluations.client_fk = ANY(:clients)
  AND evaluations.scale_fk = :scale_id
ORDER BY evaluations.created_at ASC;
"""

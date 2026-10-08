CREATE TABLE IF NOT EXISTS leituras_complexas (
    id SERIAL PRIMARY KEY,
    media_final FLOAT NOT NULL,           -- A medida principal/média
    vetor_amostras FLOAT[] NOT NULL,       -- O vetor com todas as sub-medidas
    medido_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registros_balanca (
    id SERIAL PRIMARY KEY,
    valor_visor FLOAT,                 -- O peso lido
    imagem1 TEXT NOT NULL,      -- Onde a foto foi salva
    imagem2 TEXT,      -- Onde a foto foi salva
    imagem3 TEXT,      -- Onde a foto foi salva
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

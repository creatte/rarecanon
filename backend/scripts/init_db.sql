-- ============================================================
-- RareCanon 数据库初始化脚本
-- 使用方法:
--   psql -U postgres -c "CREATE DATABASE rarecanon;"
--   psql -U postgres -d rarecanon -c "CREATE EXTENSION IF NOT EXISTS vector;"
--   psql -U postgres -d rarecanon -f init_db.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(50)  NOT NULL UNIQUE,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    role        VARCHAR(20)  NOT NULL DEFAULT 'doctor',
    hospital    VARCHAR(100),
    department  VARCHAR(100),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================
-- 2. 会话表
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(200) NOT NULL DEFAULT '新建会话',
    -- [搁置] patient_tag VARCHAR(100),  -- 患者匿名标识，未来对接HIS/EMR后启用
    status      VARCHAR(20)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived', 'deleted')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conv_user_id    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_status     ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conv_updated_at ON conversations(updated_at DESC);

-- ============================================================
-- 3. 消息表
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conv_id     UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL
                CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT        NOT NULL,
    sources     JSONB,
    feedback    VARCHAR(10)
                CHECK (feedback IS NULL OR feedback IN ('positive', 'negative')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_msg_conv_id   ON messages(conv_id);
CREATE INDEX IF NOT EXISTS idx_msg_created_at ON messages(conv_id, created_at);

-- ============================================================
-- 4. 文档表
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename    VARCHAR(500) NOT NULL,
    title       VARCHAR(500),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    version     INTEGER     NOT NULL DEFAULT 1,
    uploaded_by UUID        REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);

-- ============================================================
-- 5. 文档分块表 (pgvector)
-- ============================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id      UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER     NOT NULL,
    chunk_title VARCHAR(512),
    content     TEXT        NOT NULL,
    embedding   VECTOR(1024),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunk_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- ============================================================
-- 6. 长期记忆表
-- ============================================================
CREATE TABLE IF NOT EXISTS long_term_memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) NOT NULL DEFAULT 'session_summary',
    content     TEXT        NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ltm_user_id   ON long_term_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_ltm_embedding ON long_term_memories
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- ============================================================
-- 7. 审计日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(50) NOT NULL,
    resource    VARCHAR(100),
    detail      JSONB,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_user_id    ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at DESC);

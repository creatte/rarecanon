# pgvector 完整使用教程（Python + PostgreSQL + Java 对比）

> 本文以 RareCanon 项目的实际代码为例，逐行讲解 pgvector 在 Python (SQLAlchemy ORM) 中的使用方式，
> 并对比 Java (JDBC / MyBatis / JPA) 的等效写法，帮你理解"为什么 Python 里 `session.add()` 就能用"。

---

## 目录

1. [pgvector 是什么](#1-pgvector-是什么)
2. [PostgreSQL 端：原生 SQL 操作](#2-postgresql-端原生-sql-操作)
3. [Python 端：SQLAlchemy ORM + pgvector 库](#3-python-端sqlalchemy-orm--pgvector-库)
4. [Java 端对比：JDBC / MyBatis / JPA](#4-java-端对比jdbc--mybatis--jpa)
5. [项目实战逐行解析](#5-项目实战逐行解析)
6. [三种距离算子详解](#6-三种距离算子详解)
7. [HNSW 索引详解](#7-hnsw-索引详解)
8. [常见问题](#8-常见问题)

---

## 1. pgvector 是什么

**pgvector** 是 PostgreSQL 的一个扩展（extension），让数据库原生支持**向量（vector）**数据类型。
向量就是一串浮点数，比如 `[0.12, -0.34, 0.56, ...]`，通常由 Embedding 模型（本文用 BGE-M3）把文本编码得到。

有了 pgvector，你可以：
- 把向量**存**在 PostgreSQL 的 `vector` 列里
- 用 SQL 做**向量相似度检索**（余弦距离、欧氏距离、内积）
- 给向量列建**近似最近邻索引**（HNSW / IVFFlat），加速大规模检索

**核心概念**：pgvector 把向量变成了数据库的"一等公民"，就像 `INTEGER`、`VARCHAR` 一样，可以建索引、排序、过滤。

---

## 2. PostgreSQL 端：原生 SQL 操作

在进入 Python/Java 代码之前，先在 PostgreSQL 里把 pgvector 玩一遍，理解底层 SQL 是怎么写的。
这很重要，因为**无论 Python 还是 Java，最终发出的都是这些 SQL 语句**。

### 2.1 安装扩展

```sql
-- 每个需要使用 pgvector 的数据库都要执行一次（只需一次）
CREATE EXTENSION IF NOT EXISTS vector;
--                                      ^^^^^^
-- IF NOT EXISTS = 如果已经装过就跳过，幂等操作，不会报错
```

执行后会多出这些功能：
- 数据类型 `vector(n)` —— n 是维度，如 `vector(1024)`
- 距离算子 `<=>`（余弦距离）、`<->`（欧氏距离）、`<#>`（负内积）
- 索引访问方法 `hnsw` 和 `ivfflat`

### 2.2 建表

```sql
-- 创建一个带向量列的表
CREATE TABLE document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    --                                   ^^^^^^^^^^^^^^^^
    -- PostgreSQL 内置的 UUID 生成函数，相当于 Python 的 uuid4()
    doc_id      UUID        NOT NULL,
    chunk_index INTEGER     NOT NULL,
    content     TEXT        NOT NULL,
    embedding   VECTOR(1024),
    --          ^^^^^^^^^^^^
    -- 关键！这是一个 1024 维的向量列，维度必须匹配你的 Embedding 模型输出
    -- BGE-M3 输出 1024 维，所以这里写 VECTOR(1024)
    -- 如果维度不匹配，插入时会报错：expected 1024 dimensions, not 768
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_index)
);
```

### 2.3 插入数据

```sql
-- 插入一条带向量的记录
-- 向量用单引号括起来的数组字面量表示，前面不需要 CAST，PG 自动推断
INSERT INTO document_chunks (doc_id, chunk_index, content, embedding)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',   -- doc_id
    0,                                          -- chunk_index
    '21-羟化酶缺乏症是一种罕见的遗传性疾病...',  -- content
    '[0.0123, -0.0456, 0.0789, ...]'::vector   -- embedding（1024个浮点数）
    --                         ^^^^^^^
    -- ::vector 是 PostgreSQL 的类型转换语法，把字符串转成 vector 类型
    -- 如果不写 ::vector，PG 不知道这是 vector 还是普通字符串
);

-- 批量插入多条
INSERT INTO document_chunks (doc_id, chunk_index, content, embedding)
VALUES
    ('a0ee...', 0, '内容A', '[0.1, 0.2, ...]'::vector),
    ('a0ee...', 1, '内容B', '[0.3, 0.4, ...]'::vector),
    ('a0ee...', 2, '内容C', '[0.5, 0.6, ...]'::vector);
```

### 2.4 向量检索（最核心的部分）

```sql
-- 余弦相似度检索：找到与查询向量最相似的 top-5 条记录
SELECT
    id,
    content,
    chunk_title,
    -- 计算相似度分数（距离越小越相似）
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
    --  ^^                                         ^^^^^^^^^^
    --  <=> 是 pgvector 提供的"余弦距离"算子
    --  余弦距离范围 [0, 2]，0 表示完全相同，2 表示完全相反
    --  1 - 余弦距离 = 余弦相似度，范围 [-1, 1]，1 表示完全相同
    --  通常只想要正相似度，所以后面会用 WHERE 过滤
FROM document_chunks
WHERE embedding IS NOT NULL
  -- 排除向量为空的记录（否则距离计算结果也是 NULL）
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
  -- 按余弦距离升序排列，距离最小的排最前面（最相似）
LIMIT 5;
```

三种距离算子的 SQL 写法对比：

| 算子 | SQL 写法 | 含义 | 范围 | 越小越相似? |
|------|----------|------|------|-------------|
| 余弦距离 | `embedding <=> query_vec` | 向量夹角的余弦值 | [0, 2] | 是 |
| 欧氏距离 | `embedding <-> query_vec` | 两点间直线距离 | [0, ∞) | 是 |
| 负内积 | `embedding <#> query_vec` | 向量点积取负 | (-∞, ∞) | 是 |

### 2.5 建索引（加速检索）

```sql
-- HNSW 索引：适合高并发读、高召回率的场景
CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    --  ^^^^    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    --  索引算法  算子类型：告诉 pgvector 这个索引用余弦距离来比较向量
    --           vector_cosine_ops  → 配合 <=> 算子
    --           vector_l2_ops      → 配合 <-> 算子
    --           vector_ip_ops      → 配合 <#> 算子
    WITH (m = 16, ef_construction = 200);
    --    ^^^^^  ^^^^^^^^^^^^^^^^^^
    --    m: 每个节点的最大连接数，越大越精确但构建越慢（默认 16）
    --    ef_construction: 构建索引时的搜索深度，越大越精确但构建越慢（默认 64，通常 100-300）

-- IVFFlat 索引（备选方案，适合数据量大、允许少量精度损失的场景）
-- CREATE INDEX ON document_chunks
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
--          ^^^^^
--     lists: 聚类的簇数，通常取 sqrt(行数)
```

**HNSW vs IVFFlat 选择指南**：

| 特性 | HNSW | IVFFlat |
|------|------|---------|
| 召回率 | 高（>99%） | 中等（>95%） |
| 构建速度 | 慢 | 快 |
| 查询速度 | 快 | 中等 |
| 内存占用 | 高（图结构） | 低 |
| 适用场景 | 在线服务、高并发 | 离线批量检索 |
| 本项目选择 | **HNSW** | — |

---

## 3. Python 端：SQLAlchemy ORM + pgvector 库

### 3.1 为什么 Python 里 `session.add()` 能直接工作？

核心答案：**`pgvector` 这个 Python 库（`pip install pgvector`）给 SQLAlchemy 注册了一个自定义列类型 `pgvector.sqlalchemy.Vector`**。

这个类型做了三件事：

```
Python list ──(序列化)──> PostgreSQL vector 字面量 ──(存储)──> 磁盘
    ↓                        ↓
[0.12, 0.34]          '[0.12,0.34]'::vector

反向读取时：
磁盘 ──(读取)──> PostgreSQL vector ──(反序列化)──> Python list
                                                  ↓
                                            [0.12, 0.34]
```

这跟 `String(500)` 把 Python str ↔ PostgreSQL VARCHAR 的转换是同一种机制。
**SQLAlchemy 从设计上就允许列类型做这种双向转换**，pgvector 只是利用了这套机制。

### 3.2 安装依赖

```bash
pip install pgvector>=0.3.0          # pgvector Python 客户端
pip install "sqlalchemy[asyncio]>=2.0.35"  # SQLAlchemy 异步支持
pip install asyncpg>=0.30.0          # PostgreSQL 异步驱动
```

对应 `requirements.txt` 里的这几行：

```txt
sqlalchemy[asyncio]>=2.0.35
asyncpg>=0.30.0
pgvector>=0.3.0
```

### 3.3 数据库连接配置

```python
# backend/src/core/config.py
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # 从 .env 文件读取数据库连接参数
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "rarecanon")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "rarecanon")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    DB_POOL_SIZE: int = os.getenv("DB_POOL_SIZE", 10)
    DB_MAX_OVERFLOW: int = os.getenv("DB_MAX_OVERFLOW", 20)
    # Embedding 模型维度，建表时 Vector(dim) 用这个值
    EMBEDDING_DIM: int = os.getenv("EMBEDDING_DIM", 1024)

    @property
    def DATABASE_URL(self) -> str:
        """拼接完整的数据库连接 URL"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            #  ^^^^^^^^^^^^^^^^^
            #  dialect+driver://  格式
            #  postgresql = 数据库类型
            #  asyncpg    = 异步驱动（Python 3 asyncio）
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
```

### 3.4 引擎与 Session 创建

```python
# backend/src/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector  # ← 关键导入！这是整个机制的核心

from .config import settings

# ── 步骤 1：创建异步引擎 ──
engine = create_async_engine(
    settings.DATABASE_URL,           # postgresql+asyncpg://user:pass@host:port/db
    pool_size=settings.DB_POOL_SIZE,       # 连接池大小，默认 10
    max_overflow=settings.DB_MAX_OVERFLOW, # 池满时额外可创建的连接数，默认 20
)
# pool_size + max_overflow = 最大并发连接数 = 30

# ── 步骤 2：创建异步 Session 工厂 ──
async_session = async_sessionmaker(engine, expire_on_commit=False)
#                                            ^^^^^^^^^^^^^^^^^^^^
# 提交后不让 ORM 对象的属性过期（否则 commit 后再访问属性会重新查库）
# 设为 False 意味着 commit 后你还能直接读对象属性，不会触发额外查询
```

**Java 对比**：这一步相当于配置 HikariCP 连接池 + MyBatis SqlSessionFactory。

```java
// Java 等效：HikariCP + MyBatis
HikariConfig config = new HikariConfig();
config.setJdbcUrl("jdbc:postgresql://localhost:5432/rarecanon");
config.setUsername("rarecanon");
config.setPassword("123456");
config.setMaximumPoolSize(30);  // pool_size + max_overflow

HikariDataSource dataSource = new HikariDataSource(config);
SqlSessionFactory sessionFactory = new SqlSessionFactoryBuilder()
    .build(Resources.getResourceAsStream("mybatis-config.xml"));
// 但 pgvector 的 Vector 类型不在标准 JDBC 类型中，
// 所以 Java 里需要额外注册自定义 TypeHandler，见第 4 节
```

### 3.5 模型定义（ORM 映射）

```python
# backend/src/core/database.py

class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，所有 ORM 模型继承它"""
    pass


class Document(Base):
    """文档元数据表 —— 没有向量列，纯业务字段"""
    __tablename__ = "documents"
    #              ^^^^^^^^^^^
    # 映射到 PostgreSQL 中的表名

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    #         ^^^^^^^^^^^^^^^^^^^^
    # PostgreSQL 的 UUID 类型，映射到 Python 的 uuid.UUID 对象
    # default=uuid4 每次插入生成随机 UUID
    filename = Column(String(500), nullable=False, comment="来源文件名")
    title = Column(String(500), comment="文档标题")
    status = Column(String(20), nullable=False, default="completed")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))


class DocumentChunk(Base):
    """文档分块表 —— 核心：带 pgvector 向量列"""
    __tablename__ = "document_chunks"
    # 联合唯一约束：同一个文档下 chunk_index 不能重复
    __table_args__ = (UniqueConstraint("doc_id", "chunk_index"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id = Column(UUID(as_uuid=True),
                    ForeignKey("documents.id", ondelete="CASCADE"),
                    nullable=False)
    chunk_index = Column(Integer, nullable=False, comment="块序号")
    chunk_title = Column(String(512), comment="所属章节标题")
    content = Column(Text, nullable=False, comment="文本内容")

    # ═══════════ 核心行 ═══════════
    embedding = Column(Vector(settings.EMBEDDING_DIM), comment="dense向量")
    #                  ^^^^^^                          ^^^^^^^^^^^^^^^^
    #                  pgvector.sqlalchemy.Vector      从配置读取维度 (1024)
    #
    # 这一行做了什么？
    # 1. 声明数据库列的类型为 PG 的 vector(1024)
    # 2. 告诉 SQLAlchemy：存的时候把 Python list → vector 字面量
    # 3. 告诉 SQLAlchemy：读的时候把 vector 字面量 → Python list
    # 4. 给这个列挂载了 .cosine_distance()、.l2_distance() 等方法，用于构建查询表达式
    # ═══════════════════════════════

    metadata_ = Column("metadata", JSONB, default=dict, comment="元数据")
    #          ^^^^^^^^^^^^^^^^^^^^
    # 第一个参数 "metadata" 是数据库列名
    # 属性名 metadata_ 加了下划线，因为 Python 的 metadata 是保留字
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
```

**Java 对比：JPA Entity 写法**

```java
// Java 用 JPA + Hibernate 需要自己注册类型，没有标准做法
@Entity
@Table(name = "document_chunks")
public class DocumentChunk {
    @Id
    @GeneratedValue
    private UUID id;

    private UUID docId;
    private Integer chunkIndex;

    @Column(columnDefinition = "TEXT")
    private String content;

    // ⚠️ 问题来了：没有标准的 JPA 类型能映射 PG 的 vector
    // 你需要自己实现 Hibernate UserType 或 JPA AttributeConverter
    // @Column(columnDefinition = "vector(1024)")
    // @Convert(converter = PgVectorConverter.class)  ← 要自己写这个类！
    private float[] embedding;  // 或者用 PGvector 自定义类型
}
```

### 3.6 插入数据

```python
# backend/src/rag/ingestion.py

async def ingest_file(file_path: str) -> int:
    """入库单个 markdown 文件，返回 chunk 数量"""

    # 1. 读取文件、切分文本、生成向量（业务逻辑，略）
    chunks = chunk_markdown(text, source)              # 文本切分成块
    dense_vecs = embedding_service.encode_dense(contents)  # BGE-M3 编码成向量
    # dense_vecs 是 np.ndarray，shape = (n, 1024)，每行是一个 L2 归一化后的向量

    # 2. 写入数据库
    async with async_session() as session:
    #      ^^^^^^^^^^^^^^^^^^^^^^^^^
    # 等效于 Java 的 try-with-resources，退出时自动 commit/rollback + close
    # 等价 SQL: BEGIN;

        # ── 2a. 创建文档元数据记录 ──
        doc = Document(
            filename=source,   # 文件名，如 "罕见病指南2025.md"
            title=source,      # 标题先用文件名
            status="completed" # 标记为处理完成
        )
        # 这时 doc 还在 Python 内存中，没有发 SQL
        session.add(doc)
        #         ^^^^^^^^
        # 把 doc 对象加入 session 的待处理列表（identity map）
        # 此时仍未发 SQL！SQLAlchemy 会攒一批操作，在 flush/commit 时统一发出
        # 等价 Java: session.insert("documents", docMap);

        await session.flush()
        #             ^^^^^
        # ★ 关键一步！flush 不等于 commit
        # flush 把待处理的 SQL 发到数据库执行，但事务未提交（可以回滚）
        # flush 的目的是获取数据库生成的字段值（这里就是 doc.id）
        # flush 之后 doc.id 就可用，否则是 None
        # 等价 SQL: INSERT INTO documents (...) VALUES (...) RETURNING id;
        # （事务未提交，但当前 session 可见）

        # ── 2b. 逐条插入分块 ──
        for chunk, vec in zip(chunks, dense_vecs):
            dc = DocumentChunk(
                doc_id=doc.id,                  # flush 后拿到的 UUID
                chunk_index=chunk["chunk_index"],
                chunk_title=chunk["title"],
                content=chunk["content"],
                embedding=vec.tolist(),
                #         ^^^^^^^^^^^
                # ★ 核心：numpy array → Python list
                # vec 是 np.ndarray([0.12, -0.34, ...])，1024 个 float32
                # .tolist() 转成 Python list: [0.12, -0.34, ...]
                # SQLAlchemy 收到这个 list 后，pgvector 把它序列化成:
                #   '[0.12,-0.34,...]'::vector
                # 整个过程我们不需要写任何 SQL！
            )
            session.add(dc)
            # 同样，add 只是登记到 session，没发 SQL

        await session.commit()
        #             ^^^^^^
        # 提交事务：把所有 add 的 INSERT 一次性发给数据库，然后 COMMIT
        # 等价 SQL: COMMIT;
        #
        # ⚠️ 这个项目用的是逐条 add + 最后一次性 commit
        # 对于大批量写入，更好的做法是用 session.add_all() 或 bulk_insert_mappings()
        # 详见第 8.2 节

    return len(chunks)
```

**`session.add()` vs `session.flush()` vs `session.commit()` 关系图**：

```
session.add(obj)     →  标记对象"待插入"（在内存中排队）
        ↓
session.flush()      →  把排队的 SQL 发到数据库执行（事务未提交，可回滚）
        ↓               flush 后可以拿到 DB 生成的 ID、默认值等
session.commit()     →  提交事务（不可逆，其他连接可见）
```

**Java 对比：插入带向量的数据**

```java
// ── Java JDBC 原生写法（需要手写 SQL）──
String sql = "INSERT INTO document_chunks (doc_id, chunk_index, content, embedding) "
           + "VALUES (?, ?, ?, ?::vector)";
//                          ^   ^
//                          占位符，Java 的 PreparedStatement 用 ? 代替值

try (PreparedStatement ps = conn.prepareStatement(sql)) {
    ps.setObject(1, docId);          // UUID
    ps.setInt(2, chunkIndex);        // chunk_index
    ps.setString(3, content);        // content

    // ★ 关键差异：向量列的处理
    float[] embedding = vec.toArray();  // 拿到 float[]
    // JDBC 不知道什么是 "vector"，你需要手动建 PGobject
    PGobject pgVector = new PGobject();
    pgVector.setType("vector");         // 告诉 PG 这是 vector 类型
    pgVector.setValue(Arrays.toString(embedding));  // 转成 [0.12, -0.34, ...] 字符串
    ps.setObject(4, pgVector);          // 设置第 4 个参数

    ps.executeUpdate();  // 执行 INSERT
}
// 对比 Python：
// dc = DocumentChunk(embedding=vec.tolist())
// session.add(dc)
// ← 就这两行，比 Java 少了类型转换、字符串拼接、PreparedStatement 封装
```

```java
// ── Java MyBatis 写法 ──
// mapper.xml:
// <insert id="insertChunk">
//     INSERT INTO document_chunks (doc_id, chunk_index, content, embedding)
//     VALUES (#{docId}, #{chunkIndex}, #{content},
//             #{embedding, typeHandler=com.example.PgVectorTypeHandler}::vector)
//                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//     需要自己写一个 TypeHandler，把 float[] ↔ PG vector 互相转换！
// </insert>

// Mapper 接口:
@Insert("INSERT INTO document_chunks (...) VALUES (...)")
void insertChunk(DocumentChunk chunk);  // embedding 字段需要 TypeHandler
```

### 3.7 向量检索

```python
# backend/src/rag/retrieval.py

async def _dense_search(
    session: AsyncSession,   # 异步 session
    query_vec: np.ndarray,   # 查询向量，shape=(1024,)，L2 归一化
    top_k: int,              # 返回 top-K 条
    threshold: float,        # 相似度阈值，低于此值的结果丢弃
) -> list[dict]:
    """pgvector 余弦相似度检索"""

    # ── 构建查询表达式 ──
    stmt = (
        select(DocumentChunk)
        #     ^^^^^^^^^^^^^^
        # 等价 SQL: SELECT * FROM document_chunks
        # SQLAlchemy select() 返回一个 Select 对象，链式调用逐步构建

        .filter(DocumentChunk.embedding.isnot(None))
        #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # 等价 SQL: WHERE embedding IS NOT NULL
        # 过滤掉向量为空的行（否则 cosine_distance 返回 NULL，排序失效）

        .order_by(DocumentChunk.embedding.cosine_distance(query_vec.tolist()))
        #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # ★ 最核心的一行！
        # DocumentChunk.embedding.cosine_distance(...) 是 pgvector 库提供的表达式方法
        # 等价 SQL: ORDER BY embedding <=> '[0.12, ...]'::vector
        #
        # 调用链解析：
        #   DocumentChunk.embedding      → Column 对象（代表 embedding 列）
        #   .cosine_distance(args)       → 生成一个 Function 表达式
        #                                 内部调用 PG 的 cosine_distance 函数
        #   query_vec.tolist()           → np array → Python list

        .limit(top_k)
        # 等价 SQL: LIMIT 5
    )

    # ── 执行查询 ──
    result = await session.execute(stmt)
    #              ^^^^^^^^^^^^^
    # 异步执行，返回 Result 对象
    # 等价 SQL: SELECT ... FROM document_chunks
    #            WHERE embedding IS NOT NULL
    #            ORDER BY embedding <=> '[0.12,...]'::vector
    #            LIMIT 5;

    chunks = result.scalars().all()
    #        ^^^^^^^^^^^^^^
    # .scalars() 从结果集中提取 ORM 对象（而非元组）
    # .all() 一次性取出所有行，返回 list[DocumentChunk]

    # ── 计算相似度并过滤 ──
    items = []
    for c in chunks:
        # 对每个结果，再算一次距离（检索时 ORDER BY 已经算过了，但这里需要精确值）
        cos_dist = c.embedding.cosine_distance(query_vec.tolist())
        #          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # 在已取出的 ORM 对象上，Vector 列的 .cosine_distance() 再次计算
        # 等价 SQL（在 Python 端完成）: SELECT embedding <=> query_vec
        # 返回值：0.0 ~ 2.0 的浮点数
        #   0.0   = 完全相同（向量方向一致）
        #   1.0   = 正交（不相关）
        #   2.0   = 完全相反

        # 距离 → 相似度（1 表示完全匹配）
        similarity = 1.0 - cos_dist

        if float(similarity) >= threshold:
            # 只保留相似度 >= 阈值的结果（默认 0.7）
            items.append({
                "content": c.content,
                "title": c.chunk_title or "",
                "score": float(similarity),
            })
    return items


async def hybrid_search(
    session: AsyncSession,
    query: str,              # 用户的自然语言查询，如 "21-羟化酶缺乏症如何诊断"
    top_k: int | None = None,      # 不传就用 settings.RAG_TOP_K (8)
    threshold: float | None = None, # 不传就用 settings.RAG_SIMILARITY_THRESHOLD (0.7)
) -> list[SearchResult]:
    """混合检索：dense向量 + sparse词权重，RRF 融合"""

    # 1. 用户查询 → BGE-M3 向量化
    query_dense = embedding_service.encode_dense([query])[0]
    #             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^
    #             返回 shape (1, 1024)                    取第一行，变 (1024,)
    query_sparse = embedding_service.encode_sparse([query])[0]
    # sparse 是词权重字典，如 {"21-羟化酶缺乏症": 0.85, "诊断": 0.52}

    # 2. 先做 Dense 检索（pgvector），粗召回 top_k * 2 条
    dense_results = await _dense_search(session, query_dense, top_k * 2, threshold)

    # 3. 用 Sparse 词权重做精细重排（只在 Python 中计算，不涉及数据库）
    if query_sparse:
        results = _hybrid_score(dense_results, query_sparse,
                                settings.EMBEDDING_SPARSE_WEIGHT, top_k)
    else:
        results = dense_results[:top_k]

    return results
```

**Java 对比：向量检索**

```java
// ── Java JDBC 原生写法 ──
String sql = "SELECT id, content, chunk_title, "
           + "       1 - (embedding <=> ?::vector) AS similarity "
           + "FROM document_chunks "
           + "WHERE embedding IS NOT NULL "
           + "ORDER BY embedding <=> ?::vector "
           + "LIMIT ?";

try (PreparedStatement ps = conn.prepareStatement(sql)) {
    // ★ 又要手动处理 vector 参数
    PGobject queryVec = new PGobject();
    queryVec.setType("vector");
    queryVec.setValue(Arrays.toString(queryVecFloat));
    ps.setObject(1, queryVec);  // WHERE 里的向量
    ps.setObject(2, queryVec);  // ORDER BY 里的向量
    ps.setInt(3, topK);         // LIMIT

    ResultSet rs = ps.executeQuery();
    List<Map<String, Object>> results = new ArrayList<>();
    while (rs.next()) {
        Map<String, Object> item = new HashMap<>();
        item.put("content", rs.getString("content"));
        item.put("title", rs.getString("chunk_title"));
        item.put("score", rs.getDouble("similarity"));
        results.add(item);
    }
    return results;
}
// 对比 Python：
// stmt = select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(vec)).limit(k)
// result = await session.execute(stmt)
// ← 还是两行，无需手动处理 PGobject
```

---

## 4. Java 端对比：JDBC / MyBatis / JPA

### 4.1 三种方式的差异总结

```
Python 之路（最短）：
  Python list → session.add() → SQLAlchemy → asyncpg → PostgreSQL
  ↑ 完全透明，不需要写任何序列化代码

Java JDBC 之路（最底层）：
  float[] → Arrays.toString() → PGobject.setType("vector") → PreparedStatement.setObject() → PostgreSQL
  ↑ 每一步都要手工处理

Java MyBatis 之路（需要自定义 TypeHandler）：
  float[] → PgVectorTypeHandler → MyBatis → PreparedStatement → PostgreSQL
                  ↑
           需要自己写这个类！JDBC 标准没有 vector 类型

Java JPA/Hibernate 之路（需要自定义 UserType）：
  float[] → PgVectorUserType → Hibernate → JDBC → PostgreSQL
                ↑
         也需要自己写！社区有 hibernate-spatial，但不覆盖 pgvector
```

### 4.2 Java 要实现等效功能需要写的额外代码

如果 Java 项目要用 ORM 方式操作 pgvector（像 Python `session.add()` 那样），至少需要：

1. **自定义 TypeHandler**（MyBatis）或 **UserType**（Hibernate），实现 `float[]` ↔ PG `vector` 的转换
2. **自定义 SQL 方言函数注册**，把 `<=>`、`cosine_distance()` 等算子注册给 Hibernate/MyBatis，才能在 Criteria API 里用
3. **依赖 pgvector-java 或手动引入 PGobject**

Python 的 `pgvector` 库已经把这三件事全做了。

### 4.3 已有 pgvector 的 JDBC 驱动替代方案

```java
// pgvector 官方也提供了 JDBC 支持：
// https://github.com/pgvector/pgvector-java
// Maven:
// <dependency>
//   <groupId>com.pgvector</groupId>
//   <artifactId>pgvector</artifactId>
//   <version>0.1.6</version>
// </dependency>

// 使用方式（简化了很多但仍不如 Python 透明）：
PGvector embedding = new PGvector(floatArray);

// 但这是在 JDBC 层面的，要整合进 ORM 还是需要写 TypeHandler
```

---

## 5. 项目实战逐行解析

下面以 RareCanon 项目的完整流程为例，从初始化到检索，逐行解析。

### 5.1 初始化数据库

```python
# backend/src/core/database.py

async def init_db():
    """创建 pgvector 扩展和表"""
    async with engine.begin() as conn:
        #                               ^^^^^^^^^^
        # engine.begin() 开始一个事务，返回一个 Connection 对象
        # async with 退出时自动 commit

        # ── 步骤 A：启用 pgvector 扩展 ──
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        #    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # conn.execute() 执行原始 SQL
        # text() 把字符串包裹成 SQLAlchemy 可执行的 SQL 表达式
        # 这行只在首次启动时真正执行，之后 IF NOT EXISTS 跳过
        # 等价手动在 psql 里敲: CREATE EXTENSION IF NOT EXISTS vector;

        # ── 步骤 B：创建所有 ORM 表 ──
        await conn.run_sync(Base.metadata.create_all)
        #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # Base.metadata.create_all: 读取所有继承 Base 的类，生成 CREATE TABLE 语句
        # conn.run_sync(): 把同步的 create_all 包装成异步调用
        # 生成的 SQL 类似:
        #   CREATE TABLE documents (...);
        #   CREATE TABLE document_chunks (
        #       ...,
        #       embedding VECTOR(1024),  ← Vector 类型被自动翻译
        #       ...
        #   );
```

### 5.2 完整入库流程

```python
# backend/run_ingestion.py 或直接调用 ingest_directory()

async def main():
    await ingest_directory("backend/data/processed")
    #          ^^^^^^^^^^^^^ 遍历目录下所有 .md 文件，逐个入库
```

查看 `ingest_directory` 的逻辑（文件：`backend/src/rag/ingestion.py:133`）：

```python
async def ingest_directory(dir_path: str) -> int:
    # 1. 扫描目录下的 .md 文件
    md_files = sorted(os.path.join(dir_path, f) for f in os.listdir(dir_path)
                      if f.endswith(".md"))

    # 2. 初始化数据库（建表 + 启用 pgvector 扩展）
    await init_db()

    # 3. 逐个文件入库
    total = 0
    for i, path in enumerate(md_files, 1):
        n = await ingest_file(path)  # ← 看上面的 ingest_file 逐行解析
        total += n
    return total
```

### 5.3 完整检索流程

```python
# 从用户问题到 RAG 结果的完整链路

# 步骤 1: 用户提出问题
query = "21-羟化酶缺乏症的诊断标准是什么？"

# 步骤 2: BGE-M3 把问题编码成向量
query_dense = embedding_service.encode_dense([query])[0]
# query_dense = np.array([0.012, -0.034, ...], shape=(1024,), dtype=float32)

# 步骤 3: 在 pgvector 中检索最相似的 chunks
async with async_session() as session:
    results = await hybrid_search(session, query, top_k=5, threshold=0.7)

# 步骤 4: 把检索到的 chunks 拼接成上下文，送给 LLM 生成回答
# context = "\n\n".join(r["content"] for r in results)
# prompt = f"根据以下资料回答问题：\n{context}\n\n问题：{query}"
# answer = await llm.invoke(prompt)
```

### 5.4 混合打分（Sparse 重排）

```python
# backend/src/rag/retrieval.py

def _hybrid_score(
    dense_items: list[dict],          # Dense 检索返回的候选（pgvector cosine_distance）
    query_sparse: dict[str, float],   # 查询的问题经过 BGE-M3 sparse 头输出的词权重
    sparse_weight: float,             # sparse 权重占比，默认 0.3
    top_k: int,
) -> list[dict]:
    """RRF（倒数秩融合）变体：加权合并 Dense 和 Sparse 分数"""

    for item in dense_items:
        content_lower = item["content"].lower()
        sparse_score = 0.0

        # 计算 Sparse 分数：看查询中的关键词在文档中出现了多少
        for token, weight in query_sparse.items():
            # token 如 "21-羟化酶缺乏症"，weight 如 0.85
            if token.lower() in content_lower:
                sparse_score += weight
                # 如果文档包含这个关键词，就累加它的权重

        # 归一化：除以所有词权重的绝对值之和，得到 [0, 1] 之间的分数
        if query_sparse:
            sparse_score = sparse_score / sum(abs(w) for w in query_sparse.values())

        # 加权融合：70% dense 分数 + 30% sparse 分数
        item["score"] = (1 - sparse_weight) * item["score"] + sparse_weight * sparse_score

    # 按融合分数降序排列，取 top_k
    dense_items.sort(key=lambda x: x["score"], reverse=True)
    return dense_items[:top_k]
```

**为什么需要混合检索？**

纯 Dense 向量检索（直接用 pgvector `cosine_distance`）做语义泛化很好，但可能漏掉精确的医学术语。
比如搜"21-羟化酶缺乏症"，Dense 可能返回"先天性肾上腺皮质增生症"（相关但不精确），
而 Sparse 词权重能精确匹配到文档中出现过"21-羟化酶缺乏症"这个词的 chunks。

---

## 6. 三种距离算子详解

### 6.1 使用场景对比

| 算子 | PG 符号 | Python 方法 | 最佳适用场景 |
|------|---------|------------|-------------|
| 余弦距离 | `<=>` | `.cosine_distance()` | **语义搜索（默认选择）** |
| 欧氏距离 | `<->` | `.l2_distance()` | 图像向量、需要敏感绝对差异 |
| 负内积 | `<#>` | `.max_inner_product()` | 未归一化向量的相似度 |

### 6.2 本项目选择余弦距离的原因

```python
# BGE-M3 输出的向量做了 L2 归一化（embedding_service.encode_dense 里 normalize_embeddings=True）
# L2 归一化后：||v|| = 1（向量的模长为 1）
# 此时：余弦相似度 = 点积 = v1 · v2

# 在代码里（test_ingestion.py:132）可以看到直接用点积等效：
sim = float(np.dot(emb, query_vec))
# 等价于 1 - cosine_distance（因为 L2 归一化后余弦距离 = 1 - 点积）
```

### 6.3 如果在 Java 中要换成欧氏距离

```sql
-- SQL 层面：用 <-> 替换 <=>
SELECT *, embedding <-> '[0.1, ...]'::vector AS l2_dist
FROM document_chunks
ORDER BY embedding <-> '[0.1, ...]'::vector
LIMIT 5;
```

```python
# Python 层面：用 .l2_distance() 替换 .cosine_distance()
stmt = select(DocumentChunk).order_by(
    DocumentChunk.embedding.l2_distance(query_vec.tolist())
).limit(top_k)
# pgvector 库把三个算子都挂在了 Vector 列对象上，调用方式完全一致
```

---

## 7. HNSW 索引详解

### 7.1 索引参数含义

```sql
CREATE INDEX idx_chunk_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

| 参数 | 默认值 | 项目值 | 含义 |
|------|--------|--------|------|
| `m` | 16 | 16 | 每个节点的最大邻居数，越大 → 召回率越高，但构建更慢、内存更多 |
| `ef_construction` | 64 | 200 | 构建时搜索的候选队列长度，越大 → 索引质量越高，但构建显著变慢 |

### 7.2 查询时可调的参数

```sql
-- 在查询前设置 ef_search（默认 40），控制检索时的搜索深度
SET hnsw.ef_search = 100;
--  ef_search 越大，召回越精确，但查询越慢
--  通常设为 top_k * 4 到 top_k * 10

SELECT * FROM document_chunks
ORDER BY embedding <=> '[...]'::vector
LIMIT 5;
```

Python 端设置方式：

```python
# SQLAlchemy 中设置 ef_search
await session.execute(text("SET hnsw.ef_search = 100"))
# 然后再执行检索查询
```

### 7.3 索引维护

```sql
-- 查看索引大小
SELECT pg_size_pretty(pg_relation_size('idx_chunk_embedding'));

-- 重建索引（大量插入/删除后推荐）
REINDEX INDEX idx_chunk_embedding;
```

---

## 8. 常见问题

### 8.1 向量维度不匹配

```python
# 错误示例
chunk = DocumentChunk(
    embedding=[0.1, 0.2]  # 只有 2 维！
)
# 报错: expected 1024 dimensions, not 2

# 正确做法
chunk = DocumentChunk(
    embedding=vec.tolist()  # 确认 vec 的长度 = settings.EMBEDDING_DIM
)
```

```java
// Java 侧同样会报错
PGobject pgVector = new PGobject();
pgVector.setType("vector");
pgVector.setValue("[0.1,0.2]");  // 只有 2 个值，但 PG 列是 vector(1024)
ps.setObject(1, pgVector);
// 执行时报错: expected 1024 dimensions, not 2
```

### 8.2 大批量插入太慢

当前项目用逐条 `session.add()`，每条一个 INSERT 语句，1000 条就是 1000 个 SQL。

**优化方案 1：用 `session.add_all()`（仍然走 ORM，但减少 Python 开销）**

```python
chunks_objs = [
    DocumentChunk(
        doc_id=doc.id,
        chunk_index=chunk["chunk_index"],
        chunk_title=chunk["title"],
        content=chunk["content"],
        embedding=vec.tolist(),
    )
    for chunk, vec in zip(chunks, dense_vecs)
]
session.add_all(chunks_objs)  # 一次性注册所有对象
await session.commit()
```

**优化方案 2：用原始 SQL 的 `unnest` 批量插入（快 10-100 倍）**

```python
# 把所有 chunk 的 embedding 拼成一个大的 list
all_embeddings = [vec.tolist() for vec in dense_vecs]

await session.execute(
    text("""
        INSERT INTO document_chunks (doc_id, chunk_index, content, chunk_title, embedding)
        SELECT :doc_id, i, content, title, embedding
        FROM unnest(:contents, :titles, :embeddings::vector[])
            WITH ORDINALITY AS t(content, title, embedding, i)
    """),
    {
        "doc_id": doc.id,
        "contents": [c["content"] for c in chunks],
        "titles": [c["title"] for c in chunks],
        "embeddings": all_embeddings,  # pgvector 能识别嵌套的 Python list
    }
)
await session.commit()
```

**Java 对比：JDBC 批量插入**

```java
// Java JDBC batch insert
String sql = "INSERT INTO document_chunks (...) VALUES (?, ?, ?, ?::vector)";
try (PreparedStatement ps = conn.prepareStatement(sql)) {
    for (int i = 0; i < chunks.size(); i++) {
        ps.setObject(1, docId);
        ps.setInt(2, i);
        ps.setString(3, chunks.get(i).getContent());

        PGobject vec = new PGobject();
        vec.setType("vector");
        vec.setValue(Arrays.toString(embeddings.get(i)));
        ps.setObject(4, vec);

        ps.addBatch();  // 加入批次
        if (i % 500 == 0) {
            ps.executeBatch();  // 每 500 条执行一次
        }
    }
    ps.executeBatch();  // 执行剩余批次
}
// 和 Python unnest 方案对比，JDBC batch 仍需 1000 次网络往返，
// unnest 只需要 1 次，差距可达 10-100 倍
```

### 8.3 `expire_on_commit=False` 的作用

```python
async_session = async_sessionmaker(engine, expire_on_commit=False)
#                                            ^^^^^^^^^^^^^^^^^^^^
```

如果不设这个（默认为 True），`session.commit()` 之后，之前查出来的 ORM 对象的所有属性会被标记为"过期"。
之后再访问 `chunk.content` 会触发一次新的 SELECT。

对于本项目的流程（commit 后马上用 chunks 数据），设 False 避免不必要的查询。

### 8.4 为什么 Dense 检索时取 `top_k * 2`？

```python
# retrieval.py:30
dense_results = await _dense_search(session, query_dense, top_k * 2, threshold)
```

因为 Dense 粗召回后还要经过 Sparse 重排和阈值过滤，取 2 倍候选可以保证：
- Sparse 重排时有足够的候选空间
- 过滤掉低相似度结果后仍有 top_k 条
- 用户体验：最终返回 5 条 vs 返回 2 条（被阈值砍掉 3 条）

### 8.5 pgvector 的 `cosine_distance` 为什么不用绝对值

```python
# retrieval.py:60-61
cos_dist = c.embedding.cosine_distance(query_vec.tolist())
similarity = 1.0 - cos_dist
```

`cosine_distance` 返回的是**距离**（越小越相似），不是**相似度**（越大越相似）。
要转化成直观的相似度分数，用 `1.0 - distance`。
- distance ≈ 0 → similarity ≈ 1（几乎完全相同）
- distance = 1 → similarity = 0（正交，不相关）
- distance ≈ 2 → similarity ≈ -1（完全相反）

### 8.6 Java 中如何选择 pgvector 方案

| Java 方案 | 复杂度 | 灵活性 | 推荐场景 |
|-----------|--------|--------|---------|
| JDBC + 手写 SQL + PGobject | 中 | 最高 | 小项目、性能极致场景 |
| MyBatis + 自定义 TypeHandler | 高 | 高 | 中等项目、团队熟悉 MyBatis |
| JPA/Hibernate + UserType | 最高 | 中 | 大项目、强类型要求 |
| Spring Data JDBC + pgvector-java | 中 | 中 | 折中方案 |
| **直接用 Python 替代** | **最低** | **高** | **数据管道、RAG 服务** ← 本项目选择 |

---

## 附录：速查表

### Python 常用操作速查

```python
# 建表
class MyTable(Base):
    __tablename__ = "my_table"
    embedding = Column(Vector(1024))  # 可用 settings.EMBEDDING_DIM

# 插入
obj = MyTable(embedding=vec.tolist())  # np.ndarray → list
session.add(obj)
await session.commit()

# 检索 - 余弦相似度
stmt = select(MyTable).order_by(
    MyTable.embedding.cosine_distance(query_vec.tolist())
).limit(10)

# 检索 - 欧氏距离
stmt = select(MyTable).order_by(
    MyTable.embedding.l2_distance(query_vec.tolist())
).limit(10)

# 检索 - 内积
stmt = select(MyTable).order_by(
    MyTable.embedding.max_inner_product(query_vec.tolist())
).limit(10)

# 建索引（原始 SQL）
await session.execute(text(
    "CREATE INDEX IF NOT EXISTS idx_embedding ON my_table "
    "USING hnsw (embedding vector_cosine_ops) "
    "WITH (m = 16, ef_construction = 200)"
))
```

### Java 常用操作速查

```java
// 建表 - 无法用 ORM 自动建，建议用 SQL 脚本
// CREATE TABLE my_table (
//     id UUID PRIMARY KEY,
//     embedding VECTOR(1024)
// );

// 插入
String sql = "INSERT INTO my_table (id, embedding) VALUES (?, ?::vector)";
PGobject vec = new PGobject();
vec.setType("vector");
vec.setValue(Arrays.toString(floatArray));
ps.setObject(1, uuid);
ps.setObject(2, vec);
ps.executeUpdate();

// 检索
String sql = "SELECT *, 1 - (embedding <=> ?::vector) AS similarity "
           + "FROM my_table "
           + "ORDER BY embedding <=> ?::vector LIMIT 10";
ps.setObject(1, queryVec);
ps.setObject(2, queryVec);
ResultSet rs = ps.executeQuery();

// 建索引（原始 SQL）
Statement stmt = conn.createStatement();
stmt.execute("CREATE INDEX IF NOT EXISTS idx_embedding ON my_table "
           + "USING hnsw (embedding vector_cosine_ops) "
           + "WITH (m = 16, ef_construction = 200)");
```

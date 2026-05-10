# JWT 认证 & Alembic 迁移 —— 从零详解

> 本文基于本项目的实际代码，逐行讲解 JWT 认证体系的运作原理和 Alembic 数据库迁移工具。
> 假定你之前没用过这两样东西，我们从最基础的概念开始。

---

## 目录

### 上篇：JWT 认证

- [1. 为什么需要 JWT？](#1-为什么需要-jwt)
- [2. JWT 是什么：用比喻理解](#2-jwt-是什么用比喻理解)
- [3. JWT 的三段结构](#3-jwt-的三段结构)
- [4. 项目代码逐行解析](#4-项目代码逐行解析)
  - [4.1 工具函数 — security.py](#41-工具函数--securitypy)
  - [4.2 注册 — POST /register](#42-注册--post-register)
  - [4.3 登录 — POST /login](#43-登录--post-login)
  - [4.4 刷新 — POST /refresh](#44-刷新--post-refresh)
  - [4.5 访问受保护接口 — get_current_user](#45-访问受保护接口--get_current_user)
- [5. Access Token 和 Refresh Token 的双令牌设计](#5-access-token-和-refresh-token-的双令牌设计)
- [6. JWT 的安全边界](#6-jwt-的安全边界)

### 下篇：Alembic 迁移

- [7. 为什么需要 Alembic？](#7-为什么需要-alembic)
- [8. 核心概念](#8-核心概念)
- [9. 项目配置逐行解析](#9-项目配置逐行解析)
  - [9.1 alembic.ini](#91-alembicini)
  - [9.2 alembic/env.py](#92-alembicenvpy)
  - [9.3 版本文件](#93-版本文件)
- [10. 日常开发工作流](#10-日常开发工作流)
- [11. 本项目踩过的坑](#11-本项目踩过的坑)

---

## 1. 为什么需要 JWT？

HTTP 协议是**无状态**的。服务器处理完你的一次请求后，就忘了你是谁。

```
你：GET /api/v1/conversations
服务器：你是谁？我看不到你是谁 → 401
```

要让服务器持续"记住"你，有两种经典方案：

| 方案 | 原理 | 缺点 |
|------|------|------|
| **Session**（旧方案） | 服务器在内存里存一张"谁是谁"的表，浏览器只带一个 session_id | 服务器重启就丢失；多台服务器要共享 session（Redis），架构复杂 |
| **JWT**（本方案） | 服务器给你一张"加密身份证"，你每次请求带上它 | 服务器不能主动踢人（除非加黑名单）；token 里不能存太大数据 |

本项目用的是 JWT，因为它是 RESTful API 的行业标准，而且 FastAPI 生态支持完善。

---

## 2. JWT 是什么：用比喻理解

**JWT = 酒店房卡。**

你去酒店前台（`/login`），前台验证身份后给你一张房卡（JWT token）。之后你去健身房、游泳池、餐厅，不需要每次都出示身份证，刷卡就行。房卡里**自带信息**：

- 你是哪个房间的客人（`sub`: 用户 ID）
- 房卡什么时候过期（`exp`: 过期时间）
- 房卡是哪种类型（`type`: access / refresh）

最关键的是——这张房卡是**防伪**的。前台签名的墨水是特制的，别人仿造不了。JWT 的"防伪墨水"就是**数字签名**。

---

## 3. JWT 的三段结构

随便打开一个 token（比如登录返回的 `access_token`），它是三段字符串，用 `.` 连接：

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZWE1Yjg5MC...jH6zg.签名部分已省略
```

用颜色标识就是：

```
Header . Payload . Signature
 头部     载荷       签名
```

### 3.1 Header（头部）

Base64 解码后就是：

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

`HS256` 表示签名算法是 HMAC-SHA256，用密钥对内容做哈希，防止篡改。

### 3.2 Payload（载荷）—— 真正携带信息的部分

```json
{
  "sub": "1ea5b890-a7b5-43e4-aaa4-a90e0ce0066c",  // 用户ID（subject）
  "username": "test100",                             // 用户名
  "role": "doctor",                                  // 角色
  "exp": 1778325632,                                 // 过期时间（Unix时间戳）
  "type": "access"                                   // 令牌类型
}
```

其中 `sub`、`username`、`role` 是我们自己塞进去的，`exp` 和 `type` 是 JWT 规定的标准字段。

**重要**：Payload 只是 Base64 编码，**不是加密**！任何人都可以解码看到里面的内容。所以**不要把密码、手机号等敏感信息放在 payload 里**。

你可以自己验证：把 token 的第一段随便贴到 [jwt.io](https://jwt.io) 网站上，就能看到 payload 内容。

### 3.3 Signature（签名）—— 防篡改的关键

```
Signature = HMAC-SHA256(
    base64(Header) + "." + base64(Payload),
    密钥
)
```

服务器拿到 token 后，会用相同的密钥重新算一遍签名，如果算出来的签名和 token 里的一致，说明**这个 token 是服务器签发的，内容没有被改过**。

如果有人试图把 `"role": "doctor"` 改成 `"role": "admin"`，base64 后的 Payload 会变化。但他不知道密钥，所以算不出正确的签名。服务器验证时发现签名不匹配，直接拒绝。

**这就是 JWT 的核心——签名保证完整性，不依赖加密。**

---

## 4. 项目代码逐行解析

下面是本项目的完整 JWT 实现。我们从最底层工具函数开始，一层层往上讲。

### 4.1 工具函数 — security.py

路径：`backend/src/core/security.py`

#### 密码哈希

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

这里 `CryptContext` 是 passlib 库的核心类，它做两件事：
- 加密时：选 bcrypt 算法处理
- 验证时：从数据库中存储的哈希串里自动识别用了什么算法

**为什么不用 MD5 / SHA256 直接存密码？**

MD5 和 SHA256 是**一次性哈希**，如果两个人密码相同，哈希值也相同。而且攻击者可以提前算好常见密码的哈希表（彩虹表），直接查表破解。

bcrypt 不同：
- 它**自动加盐**，每次 hash 结果都不一样（即使密码相同）
- 它**故意很慢**，单次 hash 约 0.1 秒，暴力破解成本极高

```python
def hash_password(password: str) -> str:
    """明文 → bcrypt 哈希"""
    return pwd_context.hash(password)
```

调用 `hash_password("123456")` 得到的结果类似：

```
$2b$12$abcdefghijklmnopqrstuuDpYb.JGQwHkZ0X3p5Kq7YJl9Nf0WaG
│ │  │                       │
│ │  │                       └── 最终哈希值（31字符）
│ │  └── 盐值（22字符）
│ └── Hash 算法为 2b 版本的 bcrypt
└── bcrypt 标识
```

```python
def verify_password(plain: str, hashed: str) -> bool:
    """比对明文和哈希是否匹配"""
    return pwd_context.verify(plain, hashed)
```

`verify` 的流程：
1. 从 `hashed` 里提取盐值（存在哈希串的前 29 个字符里）
2. 用同样的盐值把 `plain` 哈希一遍
3. 比较结果是否相同

**密码在这里不是"解密"出来比的，而是"同样的盐重新 hash，看结果一不一致"。**

#### JWT 签发

```python
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """签发 access token，默认 30 分钟过期"""
    to_encode = data.copy()  # 拷贝一份，不修改原始 data
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
    )
    # expire = 现在时刻 + 30分钟
    to_encode.update({"exp": expire, "type": "access"})
    # 往 payload 里塞两个标准字段：
    #   exp: 过期时间（JWT 标准字段，库会自动校验）
    #   type: 自定义，区分 access 和 refresh

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    #     ^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #     jose.jwt   密钥（从配置文件读取）      签名算法（HS256）
```

`jwt.encode()` 内部做的事：

```
1. 把 to_encode → JSON → Base64 → Payload 段
2. 构造 Header {"alg":"HS256","typ":"JWT"} → Base64 → Header 段
3. 用密钥对 Header.Payload 做 HMAC-SHA256 → Signature 段
4. return "Header.Payload.Signature"
```

**所有在服务器端，不需要存储 token。只要密钥没泄露，签出来的 token 就是可信的。**

```python
def create_refresh_token(data: dict[str, Any]) -> str:
    """签发 refresh token，默认 7 天过期"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    # expire = 现在时刻 + 7天
    to_encode.update({"exp": expire, "type": "refresh"})
    # type 是 "refresh" 而非 "access"，后面 /refresh 端点会检查这个
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```

#### JWT 验证

```python
def decode_token(token: str) -> Optional[dict[str, Any]]:
    """验证并解码 token，无效返回 None"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        # jwt.decode() 自动做了三件事：
        # ① 验签名（Header+Payload 算出来的签名是否和 token 第三段一致）
        # ② 验过期（exp 字段是否小于当前时间）
        # ③ 解码 payload
        return payload
    except JWTError:
        # 任何一个环节失败 → 返回 None
        return None
```

这个设计是**永远不抛异常给调用方**，无效就返回 `None`，调用方自己判断。

**一个极易写错的地方**：`algorithms` 传的是什么？

```python
algorithms=[settings.JWT_ALGORITHM]  # ["HS256"]
# 不能写成 algorithm="HS256"（少了s，参数名不对）
# 不能写成 ["HS256", "none"]（允许 none 意味着攻击者可以不签名伪造 token）
```

> **安全教训**：永远不要让 `algorithms` 列表里出现 `"none"`。有漏洞就是因为攻击者改了 Header 里的 `"alg": "none"`，而服务器不做验证全盘接受了。

---

### 4.2 注册 — POST /register

路径：`backend/src/api/routes/auth.py`

```python
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
```

**请求体示例**：
```json
{
    "username": "test100",
    "email": "test100@qq.com",
    "password": "123456",
    "role": "doctor"
}
```

**第一步：查重**

```python
existing = await session.execute(
    select(User).where((User.username == body.username) | (User.email == body.email))
)
#                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# SQLAlchemy 的 OR 条件：用户名或邮箱任一重复就拒绝
# 等价 SQL: SELECT * FROM users WHERE username = 'test100' OR email = 'test100@qq.com'
if existing.scalars().first():
    raise HTTPException(status_code=409, detail="用户名或邮箱已被注册")
```

**第二步：创建用户**

```python
user = User(
    username=body.username,
    email=body.email,
    password=hash_password(body.password),  # ← 明文在这里被加密，数据库从不存明文
    role=body.role,
)
session.add(user)
await session.commit()
await session.refresh(user)  # 刷新获取数据库生成的 id 和 created_at
```

**第三步：签发令牌并返回**

```python
payload = {"sub": str(user.id), "username": user.username, "role": user.role}
access = create_access_token(payload)   # 30分钟有效
refresh = create_refresh_token(payload)  # 7天有效
return TokenResponse(access_token=access, refresh_token=refresh)
```

**注册后直接返回 token**，意味着新用户不需要再跳到登录页重新输入密码。这在实践中很常见。

---

### 4.3 登录 — POST /login

```python
@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
```

登录流程和注册第三、四步一样，区别在于前面是**验证密码**而非创建用户：

```python
result = await session.execute(
    select(User).where((User.username == body.username) | (User.email == body.email))
)
# 这里的巧思：login 的 username 字段同时支持用户名和邮箱
# 用户输入 "test100" → 匹配 username 列
# 用户输入 "test@qq.com" → 匹配 email 列
user = result.scalars().first()
```

密码验证：

```python
if not verify_password(body.password, user.password):
    raise HTTPException(status_code=401, detail="用户名或密码错误")
```

**注意**：无论用户名不存在还是密码错误，返回的提示是一样的。这是为了防止**用户枚举攻击**——攻击者不能根据错误提示区分"这个用户名存在但密码不对"和"这个用户名根本不存在"。

---

### 4.4 刷新 — POST /refresh

```python
@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="refresh_token 无效或已过期")
    if payload.get("type") != "refresh":
        # 防止有人把 access_token 拿来这个接口用
        raise HTTPException(status_code=401, detail="仅接受 refresh_token")
```

**type 检查的意义**：

| token 类型 | 有效期 | 适用范围 |
|-----------|--------|---------|
| access (`"type":"access"`) | 30分钟 | 所有需要认证的接口 |
| refresh (`"type":"refresh"`) | 7天 | 仅 `/refresh` 一个接口 |

如果攻击者拿到了 access_token（30分钟有效），他无法用 `/refresh` 续期，30 分钟后自动失效。

```python
sub_payload = {"sub": payload["sub"], "username": payload["username"], "role": payload["role"]}
new_access = create_access_token(sub_payload)
# 当前策略：refresh_token 原样返回，只签发新的 access_token
return TokenResponse(access_token=new_access, refresh_token=body.refresh_token)
```

---

### 4.5 访问受保护接口 — get_current_user

路径：`backend/src/api/deps.py`

这是 **FastAPI 依赖注入**的典型用法：

```python
async def get_current_user(authorization: str = Header(..., alias="Authorization")) -> User:
```

`Header(..., alias="Authorization")` 的意思是：从 HTTP 请求头里取 `Authorization` 字段的值，没有就自动返回 422。

如 HTTP 请求为：
```
GET /api/v1/auth/me HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

`authorization` 参数的值就是 `"Bearer eyJhbGciOiJIUzI1NiIs..."`。

```python
if not authorization.startswith("Bearer "):
    raise HTTPException(status_code=401, detail="...")
token = authorization[7:]  # 截掉 "Bearer "（正好7个字符）
```

**为什么是 `Bearer`？**

HTTP 标准（RFC 7235）定义的认证方案中，`Bearer` 含义是"持有者即可访问"。对应的 `Basic` 方案是"用户名:密码 Base64"。JWT 使用 `Bearer` 方案。

```python
payload = decode_token(token)
if payload is None:
    raise HTTPException(status_code=401, detail="token 无效或已过期")
if payload.get("type") != "access":
    raise HTTPException(status_code=401, detail="需要 access_token")
```

**三层校验全部失败都返回 401**，不给攻击者任何线索。

```python
user_id = payload.get("sub")
result = await session.execute(select(User).where(User.id == user_id))
user = result.scalars().first()
if user is None:
    raise HTTPException(status_code=401, detail="用户不存在或已被删除")
```

**为什么 decode 之后还要查一次数据库？**

因为 JWT 是无状态的——如果用户在签发 token 后被管理员删除了，之前签发的 token 签名仍然是有效的。查数据库可以保证"被删除的用户无法访问"。这一层校验不是必须的（很多系统不做），但本项目为了安全做了。

**使用方式**——在路由函数里注入：

```python
@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user  # user 是完整的 ORM 对象，可以直接返回
```

`Depends(get_current_user)` 会触发上述全部校验逻辑，通过了才执行路由函数体。如果失败，路由函数根本不会执行，直接返回 401。

---

## 5. Access Token 和 Refresh Token 的双令牌设计

### 为什么需要两种令牌？

这是一个"安全 vs 体验"的权衡：

```
如果只有一种 token：
  - 有效期短（30min）→ 用户每半小时就要重新登录 → 体验差
  - 有效期长（7天） → token 泄露后攻击者能用 7 天 → 不安全

双令牌方案：
  access_token  ：有效期短（30min），每次请求都带，即使泄露影响有限
  refresh_token ：有效期长（7天），只在 /refresh 用一次，暴露面极小
```

### 完整流程

```
┌─────────┐                    ┌──────────┐
│  前端    │                    │   后端    │
└────┬────┘                    └────┬─────┘
     │    POST /login              │
     │ ──────────────────────────> │  验证密码
     │ <────────────────────────── │  返回 access + refresh
     │                             │
     │    GET /api/xxx             │
     │    Authorization: Bearer    │
     │    <access_token>           │
     │ ──────────────────────────> │  验签名 + 验过期 → OK
     │ <────────────────────────── │  返回数据
     │                             │
     │  ... 30 分钟后 ...          │
     │                             │
     │    GET /api/xxx             │
     │    <access_token>           │
     │ ──────────────────────────> │  验签名 + 验过期 → 过期了！
     │ <────────────────────────── │  401
     │                             │
     │    POST /refresh            │
     │    <refresh_token>          │
     │ ──────────────────────────> │  验签名 + 验type → OK
     │ <────────────────────────── │  返回新的 access_token
     │                             │
     │    GET /api/xxx             │
     │    <新的 access_token>      │
     │ ──────────────────────────> │  OK
```

前端要做的是：收到 401 → 自动调 `/refresh` → 用新 token 重试原请求。这个逻辑可以封装在 axios 拦截器或 fetch 封装中。

---

## 6. JWT 的安全边界

### 6.1 JWT 保护什么？不保护什么？

| 保护 | 不保护 |
|------|--------|
| 内容**不被篡改**（签名验证） | 内容**不被看到**（只是 Base64，不是加密！） |
| 服务器**不需要存 session** | token 发出后**不能撤销**（除非加黑名单） |
| 跨域、分布式友好 | CSRF 攻击（需要额外防护） |

### 6.2 如果 token 泄露了怎么办？

这是 JWT 最大的弱点。应对措施：

1. **access_token 有效期设短**（本项目 30 分钟），泄露影响窗口小
2. **HTTPS 全站**（没人会在 HTTP 下用 JWT，纯裸奔）
3. **前端存在 httpOnly cookie 里**，不让 JS 读到（本项目暂未做，但生产环境应该做）
4. **密钥 `JWT_SECRET_KEY` 绝对不能提交到 git**（本项目默认值 `"change-me-in-production"` 提示修改）

### 6.3 密钥怎么生成？

```bash
# Linux/Mac
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

生成 64 位十六进制字符串，写入 `.env` 中 `JWT_SECRET_KEY=` 后面。生产环境和开发环境的密钥必须不同。

---

# 下篇：Alembic 数据库迁移

---

## 7. 为什么需要 Alembic？

### 7.1 没有它之前

假设你的项目已经在生产环境运行，`users` 表有 10 万条数据。现在要加一个 `last_login` 列：

```
旧做法（痛苦）：
1. 手动写 ALTER TABLE SQL
2. 在开发环境执行
3. 记录下 SQL，部署时在服务器上再执行一遍
4. 如果忘了记 → 服务器报错 → 回滚 → 心惊胆战
5. 多个人改数据库 → SQL 顺序冲突 → 不知道谁先谁后
```

### 7.2 有了它之后

```
新做法（轻松）：
1. 修改 ORM 模型，加一行 Column
2. alembic revision --autogenerate -m "add last_login"  → 自动生成迁移文件
3. alembic upgrade head  → 一键应用
4. git commit 迁移文件 → 部署时自动执行
```

Alembic 之于数据库，等于 Git 之于代码——**版本控制**。

---

## 8. 核心概念

### 8.1 迁移文件（Migration）

`backend/alembic/versions/` 目录下的每个 `.py` 文件都是一个迁移：

```
versions/
└── 01768741feb5_initial_baseline.py    # 第 1 个迁移：基线（空）
└── a1b2c3d4e5f6_add_last_login.py     # 第 2 个迁移：加列
└── f6e5d4c3b2a1_add_conversations.py  # 第 3 个迁移：建新表
```

每个迁移文件都有两个函数：

```python
def upgrade():   # 升级：应用本次变更
    op.add_column('users', sa.Column('last_login', sa.DateTime()))

def downgrade():  # 降级：撤销本次变更
    op.drop_column('users', 'last_login')
```

### 8.2 版本链（Revision Chain）

每个迁移都记录了自己的"父版本"（`down_revision`），形成一个单向链：

```
01768741feb5  →  a1b2c3d4e5f6  →  f6e5d4c3b2a1
  (基线)          (加列)            (建表)

alembic upgrade head:  从当前版本一路执行到最新
alembic downgrade -1:  回退一个版本
```

### 8.3 alembic_version 表

Alembic 在数据库里建了一张 `alembic_version` 表，只有一行一列，记录当前数据库处于哪个版本。这就是它判断"数据库和代码谁新谁旧"的依据：

```sql
SELECT * FROM alembic_version;
-- 01768741feb5
```

---

## 9. 项目配置逐行解析

### 9.1 alembic.ini

路径：`backend/alembic.ini`

```ini
[alembic]
script_location = %(here)s/alembic
# 告诉 Alembic 迁移脚本在哪里。%(here)s = 这个 ini 文件所在的目录

prepend_sys_path = .
# 把当前目录加入 Python 的 sys.path，这样 env.py 里能 import 项目代码

sqlalchemy.url =
# 故意留空！因为我们的数据库 URL 是动态从 settings 读取的（见 env.py）
# 如果写死在这里，开发/测试/生产环境用同一个 URL，会出事
```

### 9.2 alembic/env.py

这是 Alembic 的"中枢神经"，每次 `alembic` 命令都会执行它。

```python
# 第 14 行：把 backend/src 加到 Python 搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
# os.path.dirname(__file__)  = backend/alembic
# ".."                        = backend
# "src"                        = backend/src

# 第 16-17 行：从项目代码导入
from src.core.database import Base         # ORM 基类，包含所有表的元数据
from src.core.config import settings        # 数据库连接参数
```

```python
# 第 20 行：导入 models 包
import src.models  # noqa: F401
# 为什么这里要 import？
# 因为 autogenerate 需要对比 Base.metadata 和数据库实际结构
# 如果 models 没被 import，Base.metadata 是空的，autogenerate 什么也检测不到
# noqa: F401 告诉 linter "我知道这个 import 没直接使用，别报"
```

```python
# 第 25-26 行：用配置覆盖 alembic.ini 里的空 URL
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

```python
# 第 32 行：告诉 autogenerate 以 Base.metadata 为准
target_metadata = Base.metadata
# autogenerate 做的事情：
# ① 连上数据库，读取当前所有表、列、索引的结构
# ② 读取 target_metadata（ORM 模型定义的结构）
# ③ 差异 → 生成 migration 文件
```

**两种运行模式**：

```python
def run_migrations_offline():
    """生成 SQL 脚本到文件，不连接数据库（适合 CI/CD 审核 SQL）"""
    # 用法：alembic upgrade head --sql > migration.sql

def run_migrations_online():
    """连接数据库直接执行（日常开发用这个）"""
    connectable = async_engine_from_config(
        ...,
        poolclass=pool.NullPool,  # NullPool：不建连接池，单次连接用完就关
    )
```

`poolclass=pool.NullPool` 的含义：迁移是一次性操作，不需要连接池复用的开销，用完即弃。

### 9.3 版本文件

```python
# alembic/versions/01768741feb5_initial_baseline.py

revision: str = '01768741feb5'             # 本版本的 ID（唯一标识）
down_revision: Union[str, ...] = None      # 父版本 ID。None = 这是第一个迁移

def upgrade():
    pass  # 基线迁移什么都不做（数据库已经由 init_db.sql 创建好）

def downgrade():
    pass  # 同样什么都不做
```

后续如果有变更，`upgrade()` 里会是 `op.add_column()`、`op.create_table()` 等操作。

---

## 10. 日常开发工作流

### 场景一：修改表结构

```bash
# 1. 修 ORM 模型（比如在 User 类里加一个 last_login_at 列）

# 2. 生成迁移
cd backend
alembic revision --autogenerate -m "add last_login_at to users"

# 3. 检查生成的迁移文件是否正确（重要！别直接盲目执行）
cat alembic/versions/xxxx_add_last_login_at_to_users.py

# 4. 应用迁移
alembic upgrade head

# 5. 验证
alembic current   # 显示当前数据库的版本
```

### 场景二：回退

```bash
# 回退到上一个版本
alembic downgrade -1

# 回退到指定版本
alembic downgrade 01768741feb5

# 回退到初始状态（所有表都会删掉！）
alembic downgrade base
```

### 场景三：查看状态

```bash
alembic current      # 当前数据库在哪个版本
alembic history      # 所有迁移的版本链
alembic heads        # 最新的版本（可以有多个分支）
```

### 场景四：部署时

```bash
# CI/CD 脚本或 Docker 启动命令中加一行
alembic upgrade head

# 如果数据库已经是最新版本 → 什么都不做
# 如果数据库落后 → 按顺序执行所有未应用的迁移
```

---

## 11. 本项目踩过的坑

### 坑 1：autogenerate 会生成"删索引"的操作

本项目的 HNSW 索引（`idx_chunk_embedding`）和功能性 DESC 索引（`idx_audit_created_at`）是在 `init_db.sql` 中手写的，ORM 模型无法表达。所以 Alembic 认为这些索引"在 ORM 中没有定义 → 应该删除"。

**解决**：这些特殊索引用基线迁移（空 upgrade/downgrade）标记为"已知现状"，后续不自动管理。

### 坑 2：`server_default` vs `default`

```python
# SQL 定义：created_at TIMESTAMPTZ NOT NULL DEFAULT now()
# ORM 要匹配，必须用 server_default（数据库端默认值）而不是 default（Python端默认值）
created_at = Column(DateTime(timezone=True), server_default=text("now()"))
```

如果用 `default=datetime.now`，Alembic 会检测到差异并尝试修改列。

### 坑 3：autogenerate 不是银弹

`--autogenerate` 能检测的类型变更有限：

| 能检测 | 不能检测 |
|--------|---------|
| 新增/删除列 | 列重命名（会变成"删旧列 + 加新列"） |
| 新增/删除表 | 表重命名 |
| 新增/删除索引 | 修改索引参数 |
| 修改 nullable | CHECK 约束变更 |

**所以每次生成迁移后必须人工检查，不能盲目信任。**

---

## 附录：速查命令

```bash
# Alembic
alembic revision --autogenerate -m "描述"   # 生成迁移
alembic upgrade head                        # 应用所有迁移
alembic downgrade -1                        # 回退一个版本
alembic current                             # 当前版本
alembic history                             # 版本历史

# JWT 密钥生成
python -c "import secrets; print(secrets.token_hex(32))"

# 手动解码 JWT 查看内容（不验证签名）
echo "eyJhbGci..." | cut -d'.' -f2 | base64 -d 2>/dev/null | python -m json.tool
```

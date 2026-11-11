# Security Architecture, Permissions & Tenant Isolation

## 1. Threat Model & Principles

LumenEIOS handles sensitive educational records, student baseline trajectories, and assessment evaluations. The system enforces strict defense-in-depth principles:
- **Zero Frontend Trust**: Frontend route guards and UI button disabling are treated as UX aids only. Every single write and read operation is authoritatively validated by backend dependency injection.
- **Strict Tenant Separation**: Cross-school campus boundaries are enforced at the database query level.
- **Cryptographic Integrity**: All credentials use bcrypt password hashing with unique salts.
- **Audit Logging**: Every sensitive mutation is recorded immutably with timestamp, user ID, and action metadata.

---

## 2. Role-Based Access Control (RBAC) Matrix

The system models five standard educational personas:

| Capability / Endpoint | Admin | Principal | Teacher | Student | Parent |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Manage Institutions & System Users** | Yes | No | No | No | No |
| **Global State-Wide Analytics** | Yes | No | No | No | No |
| **View Audit Trail Logs** | Yes | No | No | No | No |
| **Assign Class Teachers** | Yes | Yes | No | No | No |
| **Record Lost Instructional Days** | Yes | Yes | Yes | No | No |
| **Approve Syllabus Compression** | Yes | Yes | Yes | No | No |
| **Create Assessments & Cycles** | Yes | Yes | Yes | No | No |
| **Grade Assessment Sheets (OCR / Manual)** | Yes | No | Yes | No | No |
| **Submit Differentiated Homework** | No | No | No | Yes | No |
| **View Own Child Progress & Feedback** | No | No | No | No | Yes |

---

## 3. Multi-School Tenant Isolation

Schools operate as distinct tenant domains. The active school context is resolved via `get_current_school_context`:

```python
async def get_current_school_context(
    x_school_id: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> str:
    target = x_school_id or current_user.school_id or "school-1"
    
    if current_user.role == "admin":
        return target  # State admin can inspect any school
        
    if current_user.school_id == target:
        return target
        
    # Check multi-campus memberships
    result = await db.execute(
        select(SchoolMembership).filter(
            SchoolMembership.user_id == current_user.id,
            SchoolMembership.school_id == target,
            SchoolMembership.is_active == True
        )
    )
    if result.scalars().first():
        return target

    raise HTTPException(status_code=403, detail="Unauthorized school context access.")
```

---

## 4. Token Architecture & Session Management

- **Access Token**: JWT encoded with HMAC-SHA256 (`HS256`) containing `sub` (User ID), `role`, `school_id`, `iat`, and `exp` (120 minutes validity).
- **Refresh Token**: Long-lived token (7 days) for session rotation.
- **Demo Mode Transparency**: In development demonstration mode, demo accounts authenticate with `demo123` and receive valid signed JWT tokens. When `DEMO_MODE=false`, strict cryptographic hashing is enforced.


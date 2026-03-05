# Web Bank Node Application — Regulator-Ready Reference Architecture

This document turns the proposed model into an implementation-ready architecture with clear separation of concerns, secure credentialing, and auditable control points.

## 1) System Objective

The **Web Bank Node** is a regulated transaction orchestration service. It is not a direct ledger UI and not a generic web app.

Core duties:

1. Accept authenticated transaction intents.
2. Enforce allocation and policy constraints.
3. Persist immutable ledger events.
4. Publish real-time oversight telemetry.
5. Provide auditor-safe UI read models.

## 2) Topology: Control Plane vs Data Plane

```text
┌──────────────────────────────────────────────────────────────┐
│                        Control Plane                         │
│ IAM • KMS • Secret Manager • Policy Registry • CI/CD         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                          Data Plane                          │
│ UI (React) -> WAF/API Gateway -> Bank Node API (Java)       │
│                              |                |              │
│                              v                v              │
│                         Spanner Ledger   Pub/Sub Oversight   │
│                                                |             │
│                                                v             │
│                                             Firestore        │
└──────────────────────────────────────────────────────────────┘
```

### Segregation rules

- UI has no direct database write privileges.
- Gateway enforces OAuth2/JWT, mTLS, DLP, and rate limiting.
- Bank Node is the only service that writes authoritative ledger events.
- Firestore is for oversight visualization only; not authoritative.

## 3) Security and Identity Model

- Use workload identity and short-lived credentials only.
- Use dedicated service accounts per workload (least privilege).
- Keep secrets in Secret Manager (never in source control).
- Encrypt data with CMEK where policy requires.
- Log admin and data-access actions to immutable audit logs.

## 4) Transaction Lifecycle

1. Client submits signed `TransactionIntent` with idempotency key.
2. Gateway validates token, route policy, and traffic controls.
3. Bank Node validates schema, auth claims, and allocation envelope.
4. Policy engine produces deterministic decision + `policy_hash`.
5. Ledger append writes immutable event with hash chaining.
6. Oversight event publishes to Pub/Sub.
7. Read model updates for UI status surfaces.

## 5) Data Model

### 5.1 Authoritative Ledger (Spanner)

```sql
CREATE TABLE ledger_event (
  event_id STRING(64) NOT NULL,
  allocation_id STRING(64) NOT NULL,
  idempotency_key STRING(128) NOT NULL,
  amount NUMERIC NOT NULL,
  currency STRING(3) NOT NULL,
  policy_hash STRING(128) NOT NULL,
  prev_event_hash STRING(128),
  event_hash STRING(128) NOT NULL,
  actor_principal STRING(256) NOT NULL,
  decision STRING(32) NOT NULL,
  created_at TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY (event_id);
```

Recommended constraints:

- Unique index on `(allocation_id, idempotency_key)`.
- Disallow updates/deletes at application layer.
- Background reconciliation verifies hash chain integrity.

### 5.2 Oversight Stream (Pub/Sub → Firestore)

- Topic: `oversight.transaction-events`
- Payload: non-sensitive summary only.
- Firestore collection: `oversight_events` with TTL policy.

## 6) Java Service Contract (Example)

```java
public final class BankNodeService {

    private final LedgerWriter ledger;
    private final OversightPublisher publisher;
    private final PolicyEngine policyEngine;

    public BankNodeService(LedgerWriter ledger,
                           OversightPublisher publisher,
                           PolicyEngine policyEngine) {
        this.ledger = ledger;
        this.publisher = publisher;
        this.policyEngine = policyEngine;
    }

    public TransactionResult process(TransactionIntent intent) {
        AllocationPolicy policy = policyEngine.evaluate(intent);

        if (ledger.exists(intent.idempotencyKey())) {
            return TransactionResult.duplicate();
        }

        LedgerEvent event = ledger.append(intent, policy);
        publisher.publish(event.toOversightSummary());

        return TransactionResult.accepted(event.eventHash());
    }
}
```

## 7) UI/UX Requirements for Regulated Operation

- Read-only default for operational users.
- Every transaction shows:
  - source allocation,
  - applied policy/version,
  - event hash.
- Explicit approval flows for threshold breaches.
- Separate oversight dashboards from admin policy screens.
- Figma assets are design-time only; never embedded in production runtime.

## 8) Non-Negotiable Anti-Patterns to Eliminate

- Hard-coded OAuth client secrets.
- Long-lived static credentials in code or container image.
- Direct UI -> database writes.
- Co-locating UI rendering logic with infra control SDK logic.
- Unsanitized embed scripts in production banking surfaces.

## 9) Compliance Mapping Starter (SOC/FFIEC/OCC-oriented)

- Access controls: least privilege, MFA, periodic entitlement review.
- Change management: reviewed PRs, signed artifacts, deploy provenance.
- Logging/monitoring: immutable audit trails with alert routing.
- Data integrity: append-only ledger + hash-chain verification.
- Incident response: runbooks, severity definitions, test exercises.

## 10) Delivery Backlog

1. Architecture diagram package (SVG/PDF).
2. Spanner + Firestore schema and migration scripts.
3. Terraform for Cloud Run, IAM, KMS, Pub/Sub, Firestore.
4. Control mapping matrix (SOC 2, FFIEC CAT domains, OCC expectations).
5. Figma-to-production UX specification with role-based states.

